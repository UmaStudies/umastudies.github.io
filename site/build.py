"""
UmaStudies build script.
Converts markdown character studies into styled static HTML pages.
Generates an index page listing all published studies.
"""

import os
import re
import json
import math
import hashlib
import html as html_lib
from pathlib import Path
from datetime import datetime, timezone
from email.utils import format_datetime

import markdown


BASE_DIR = Path(__file__).parent
CONTENT_DIR = BASE_DIR / "content" / "studies"
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DIST_DIR = BASE_DIR / "dist"

SITE_TITLE = "UmaStudies"
SITE_TITLE_JP = "ウマスタディーズ"
SITE_DESCRIPTION = "In-depth character studies on Umamusume: Pretty Derby"
SITE_AUTHOR = "Isackj07"

# Formspree endpoint for the reader feedback form (e.g. https://formspree.io/f/abc123).
# Leave empty to omit the form entirely. This is a public endpoint, not a secret.
FEEDBACK_FORM_ACTION = "https://formspree.io/f/mwvzgndg"

# Public base URL of the deployed site. Used for absolute share-image and RSS
# links. Org Pages site served at the domain root (no project subpath). Change
# this if a custom domain is added later.
SITE_URL = "https://umastudies.github.io"

# Google Search Console ownership token. Leave empty to omit. When set (paste
# only the content value from the "HTML tag" verification method), a
# google-site-verification meta tag is emitted on every page. Not a secret.
GOOGLE_SITE_VERIFICATION = "SPSBdVI6zz76B4WefzfPsgfoS36OBi77laV7msCty68"

# Upcoming studies shown in the "Coming soon" section on the index.
# Each entry: {"name": "Display Name", "name_jp": "日本語", "note": "optional line"}.
PLANNED_STUDIES = []


# Landing-page hero background. Optimized card art from static/images/hero-cards
# is arranged either as a scrolling film strip (ordered, a record of stories) or
# a drifting card field (scattered, dreamlike). Index page only.
#   HERO_MODE         default effect: "filmstrip" | "drift" | "off"
#   HERO_SHOW_TOGGLE  render an on-page Film/Drift/Off switch to compare modes.
#                     This is the instant kill switch and the prototype control;
#                     set False for production once a mode is locked in.
#   HERO_ROWS         number of film-strip rows.
#   HERO_DRIFT_COUNT  number of cards floating in drift mode.
# The effect degrades to a still field when JS is off, a card image 404s, or the
# visitor requests reduced motion. Setting HERO_MODE="off" (toggle off too)
# emits no stage markup at all and restores the plain hero.
HERO_MODE = "filmstrip"
HERO_SHOW_TOGGLE = True
HERO_ROWS = 3
HERO_DRIFT_COUNT = 8
HERO_CARDS_DIR = "static/images/hero-cards"


# Per-character theatrical effects. Each study is its own pocket dimension: a
# flourish belongs to exactly one character and must not bleed onto another.
# Effects are opt-in here by slug. Anything not listed gets a clean page driven
# only by its own CSS palette. Keys:
#   embers      -- floating ember particles
#   gem         -- rotating gemstone progress indicator (bottom right)
#   pleochroic  -- scroll-driven accent hue shift (overrides the CSS accent)
#   flame_quotes-- blockquote borders flicker like flame
CHARACTER_FX = {
    "mejiro-ramonu": {
        "embers": True,
        "gem": True,
        "pleochroic": True,
        "flame_quotes": True,
    },
}


# Front matter delimiter. Each .md study file should start with a YAML-like
# block between --- markers containing metadata.
FRONT_MATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Markdown extensions for rich rendering
MD_EXTENSIONS = ["tables", "fenced_code", "smarty", "attr_list"]


def parse_front_matter(text: str) -> tuple[dict, str]:
    """Extract front matter metadata and body from a markdown file.

    Front matter format:
      ---
      title: Mejiro Ramonu
      title_jp: ...
      character: mejiro-ramonu
      excerpt: One-line summary
      date: 2026-06-01
      ---
    """
    meta = {}
    match = FRONT_MATTER_PATTERN.match(text)
    if match:
        for line in match.group(1).strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                meta[key.strip()] = value.strip()
        body = text[match.end():]
    else:
        body = text
    return meta, body


def estimate_reading_time(text: str) -> int:
    """Rough word count based reading time in minutes.
    Accounts for CJK characters at ~2.5 chars per word equivalent.
    """
    # Count latin words
    latin_words = len(re.findall(r"[a-zA-Z]+", text))
    # Count CJK characters (each ~0.4 words for reading speed)
    cjk_chars = len(re.findall(r"[\u3000-\u9fff\uf900-\ufaff]", text))
    total_words = latin_words + (cjk_chars * 0.4)
    return max(1, math.ceil(total_words / 200))


def word_count(text: str) -> int:
    """Approximate total word count including CJK."""
    latin = len(re.findall(r"[a-zA-Z]+", text))
    cjk = len(re.findall(r"[\u3000-\u9fff\uf900-\ufaff]", text))
    return latin + math.ceil(cjk * 0.4)


def extract_toc(html: str) -> list[dict]:
    """Pull h2 and h3 elements to build a table of contents."""
    toc = []
    for match in re.finditer(r"<(h[23])[^>]*id=[\"']([^\"']+)[\"'][^>]*>(.*?)</\1>", html):
        level = match.group(1)
        slug = match.group(2)
        # Strip any inner HTML tags from the heading text
        text = re.sub(r"<[^>]+>", "", match.group(3))
        toc.append({"level": level, "id": slug, "text": text})
    return toc


def add_heading_ids(html: str) -> str:
    """Add id attributes to h2 and h3 elements for anchor linking."""

    def slugify(text: str) -> str:
        text = re.sub(r"<[^>]+>", "", text)
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s-]+", "-", text)
        return text.strip("-")

    def replacer(match):
        tag = match.group(1)
        content = match.group(2)
        slug = slugify(content)
        return f'<{tag} id="{slug}">{content}</{tag}>'

    return re.sub(r"<(h[23])>(.*?)</\1>", replacer, html)


# A markdown image that sits alone in its own paragraph, e.g.
#   <p><img alt="..." src="..." title="..." /></p>
# Python-Markdown emits self-closing img tags wrapped in a paragraph.
STANDALONE_IMG_PATTERN = re.compile(r"<p>\s*(<img\b[^>]*?/?>)\s*</p>")


def _img_attr(tag: str, name: str) -> str:
    """Pull a double-quoted attribute value out of an img tag, or empty string."""
    match = re.search(name + r'="([^"]*)"', tag)
    return match.group(1) if match else ""


def enhance_images(html: str) -> str:
    """Promote standalone markdown images to styled figures.

    Turns a paragraph-wrapped image into a <figure> with an optional caption
    (taken from the markdown title, falling back to alt text), adds lazy
    loading, and carries any attr_list class (e.g. {: .wide }) onto the figure.
    """

    def replace(match):
        tag = match.group(1)
        src = _img_attr(tag, "src")
        if not src:
            return match.group(0)
        alt = _img_attr(tag, "alt")
        img_class = _img_attr(tag, "class")
        # Caption comes only from the markdown title. alt is kept on the img
        # for accessibility, but is not duplicated as a visible caption.
        caption = _img_attr(tag, "title")

        # Carry any attr_list classes (e.g. {: .wide }, {: .pleochroic })
        # from the markdown image onto the figure wrapper.
        fig_class = "study-figure"
        extra = " ".join(c for c in img_class.split() if c)
        if extra:
            fig_class += " " + extra

        new_img = (
            f'<img src="{src}" alt="{alt}" loading="lazy" decoding="async">'
        )
        if caption:
            return (
                f'<figure class="{fig_class}">{new_img}'
                f"<figcaption>{caption}</figcaption></figure>"
            )
        return f'<figure class="{fig_class}">{new_img}</figure>'

    return STANDALONE_IMG_PATTERN.sub(replace, html)


# Matches top-level "Part N — Title" headings so they can get a ceremonial
# opener (eyebrow label + ghosted numeral). Run AFTER extract_toc so the table
# of contents keeps the original plain heading text.
PART_HEADING_PATTERN = re.compile(r'<h2 id="([^"]+)">(Part\s+\w+)\s*[—,]\s+(.*?)</h2>')


def format_part_headings(html: str) -> str:
    """Restructure 'Part N — Title' h2s into a ceremonial opener.

    Splits the heading into an eyebrow label ('Part 2'), the title, and a large
    faded numeral. Non-Part headings (Thesis, Appendix) are left untouched.
    """

    def replace(match):
        hid = match.group(1)
        label = match.group(2).strip()
        title = match.group(3).strip()
        num = label.split()[-1]
        return (
            f'<h2 id="{hid}" class="part-heading">'
            f'<span class="part-num" aria-hidden="true">{num}</span>'
            f'<span class="part-eyebrow">{label}</span>'
            f'<span class="part-title">{title}</span>'
            "</h2>"
        )

    return PART_HEADING_PATTERN.sub(replace, html)


# Markdown emits bare <table> elements with no wrapper. Wrapping each in a
# horizontally scrollable container keeps the wide bilingual appendix table
# from overflowing or crushing its columns on narrow (mobile) viewports.
TABLE_PATTERN = re.compile(r"<table>(.*?)</table>", re.DOTALL)


def wrap_tables(html: str) -> str:
    """Wrap each table in a horizontal-scroll container for mobile."""
    return TABLE_PATTERN.sub(
        r'<div class="table-scroll"><table>\1</table></div>', html
    )


def render_feedback(title_safe: str) -> str:
    """Render the reader feedback form, or empty string if no endpoint is set.

    Uses a Formspree POST form. The hidden _gotcha field is a honeypot that
    silently drops bot submissions. No JavaScript required.
    """
    if not FEEDBACK_FORM_ACTION:
        return ""
    return (
        '<section class="feedback">'
        "<h2>Spotted an error? Have a reading to share?</h2>"
        "<p>The Japanese is the authority text and I am not a native speaker. "
        "If you catch a mistranslation, or want to share how you read her, send it here.</p>"
        f'<form class="feedback-form" action="{FEEDBACK_FORM_ACTION}" method="POST">'
        '<input type="text" name="_gotcha" tabindex="-1" autocomplete="off" '
        'aria-hidden="true" style="display:none">'
        f'<input type="hidden" name="_subject" value="UmaStudies feedback: {title_safe}">'
        '<label class="feedback-field">Your thoughts or correction'
        '<textarea name="message" rows="5" required></textarea></label>'
        '<label class="feedback-field">Email (optional, for a reply)'
        '<input type="email" name="email" autocomplete="email"></label>'
        "<button type=\"submit\">Send</button>"
        "</form>"
        "</section>"
    )


def render_toc_html(toc: list[dict]) -> str:
    """Render table of contents as HTML."""
    if not toc:
        return ""
    lines = ['<nav class="study-toc" aria-label="Table of Contents">']
    for item in toc:
        css_class = "toc-h3" if item["level"] == "h3" else ""
        lines.append(
            f'  <a href="#{item["id"]}" class="{css_class}">{item["text"]}</a>'
        )
    lines.append("</nav>")
    return "\n".join(lines)


def load_template(name: str) -> str:
    """Load an HTML template file."""
    path = TEMPLATE_DIR / name
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


_CSS_VERSION = None


def css_version() -> str:
    """Short content hash of main.css for cache-busting the stylesheet URL.

    GitHub Pages serves static assets with a 10 minute cache and no version in
    the URL, so browsers (iOS Safari especially) keep serving a stale main.css
    across deploys. Appending ?v=<hash> makes each CSS change a new URL.
    Computed once per build and cached.
    """
    global _CSS_VERSION
    if _CSS_VERSION is None:
        css_path = STATIC_DIR / "css" / "main.css"
        try:
            _CSS_VERSION = hashlib.sha1(css_path.read_bytes()).hexdigest()[:8]
        except OSError:
            # No stylesheet on disk is a real build problem, but versioning is
            # not the place to fail the build. Fall back to an unversioned URL.
            _CSS_VERSION = ""
    return _CSS_VERSION


def render_template(template: str, context: dict) -> str:
    """Simple placeholder replacement. Uses {{key}} syntax."""
    result = template
    for key, value in context.items():
        result = result.replace("{{" + key + "}}", str(value))
    # Cache-bust the stylesheet so deploys are picked up immediately.
    version = css_version()
    if version:
        result = result.replace(
            'href="static/css/main.css"',
            f'href="static/css/main.css?v={version}"',
        )
    return result


def page_url(path: str) -> str:
    """Absolute URL for a page given its dist-relative path.

    Empty path returns the site root. Returns empty string when SITE_URL is
    unset, so callers can omit absolute-only markup (canonical, og:url).
    """
    base = SITE_URL.rstrip("/")
    if not base:
        return ""
    return f"{base}/{path}" if path else f"{base}/"


def build_seo_head(canonical_path: str, jsonld: dict | None = None) -> str:
    """Build the shared SEO <head> block for a page.

    Emits canonical + og:url only when SITE_URL is set (they must be absolute).
    og:site_name and og:locale are always safe. Optional JSON-LD is serialized
    as a structured-data script. Returns markup ready to drop into {{seo_head}}.
    """
    parts = []
    if GOOGLE_SITE_VERIFICATION:
        parts.append(
            '<meta name="google-site-verification" content="'
            f'{html_lib.escape(GOOGLE_SITE_VERIFICATION, quote=True)}">'
        )
    url = page_url(canonical_path)
    if url:
        parts.append(f'<link rel="canonical" href="{html_lib.escape(url, quote=True)}">')
        parts.append(f'<meta property="og:url" content="{html_lib.escape(url, quote=True)}">')
    parts.append(f'<meta property="og:site_name" content="{html_lib.escape(SITE_TITLE)}">')
    parts.append('<meta property="og:locale" content="en_US">')
    if jsonld:
        parts.append(
            '<script type="application/ld+json">'
            + json.dumps(jsonld, ensure_ascii=False)
            + "</script>"
        )
    return "\n  ".join(parts)


def build_study(md_path: Path) -> dict:
    """Convert a single markdown study to HTML. Returns metadata for the index."""
    with open(md_path, "r", encoding="utf-8") as f:
        raw = f.read()

    meta, body = parse_front_matter(raw)

    # Required metadata with fallbacks
    title = meta.get("title", md_path.stem.replace("-", " ").title())
    title_jp = meta.get("title_jp", "")
    character = meta.get("character", md_path.stem)
    excerpt = meta.get("excerpt", "")
    date_str = meta.get("date", datetime.now().strftime("%Y-%m-%d"))
    subtitle = meta.get("subtitle", "")
    epithet = meta.get("epithet", "")
    epigraph_jp = meta.get("epigraph_jp", "")
    epigraph_en = meta.get("epigraph_en", "")

    # Strip the first H1 from the body (the template renders title from front matter)
    body = re.sub(r"^#\s+[^\n]+\n*", "", body, count=1)
    # Also strip the italic subtitle line if present (already in front matter)
    body = re.sub(r"^\*[^*]+\*\s*\n*", "", body, count=1)

    # Convert markdown to HTML
    md_converter = markdown.Markdown(extensions=MD_EXTENSIONS)
    content_html = md_converter.convert(body)

    # Add heading IDs, promote images to figures, then extract TOC
    content_html = add_heading_ids(content_html)
    content_html = enhance_images(content_html)
    toc = extract_toc(content_html)
    toc_html = render_toc_html(toc)
    # Collapsed contents block shown only on small screens (the floating
    # sidebar TOC is hidden there). Native <details>, no JavaScript.
    mobile_toc_html = (
        '<details class="mobile-toc"><summary>Contents '
        '<span class="mobile-toc-jp">目次</span></summary>'
        f"{toc_html}</details>"
        if toc
        else ""
    )
    # Ceremonial Part openers. After TOC extraction so the TOC text stays plain.
    content_html = format_part_headings(content_html)
    # Wrap tables so the wide appendix scrolls instead of overflowing on mobile.
    content_html = wrap_tables(content_html)

    # Reading stats
    reading_min = estimate_reading_time(body)
    words = word_count(body)

    # Per-character theatrics. Only emit the markup/attributes for effects this
    # character opts into, so one study's flourishes never appear on another.
    fx = CHARACTER_FX.get(character, {})
    embers_html = (
        '\n  '.join('<div class="ember" aria-hidden="true"></div>' for _ in range(6))
        if fx.get("embers")
        else ""
    )
    progress_gem_html = (
        '<div class="progress-gem" id="progress-gem" aria-hidden="true"></div>'
        if fx.get("gem")
        else ""
    )
    # Body data attributes read by the inline JS / CSS to gate scroll effects.
    body_fx = ""
    if fx.get("pleochroic"):
        body_fx += ' data-fx-pleochroic="true"'
    if fx.get("flame_quotes"):
        body_fx += ' data-fx-flame="true"'

    # Render into study template
    template = load_template("study.html")
    header_image = meta.get("header_image", "")
    # Only emit the background art layer when a header_image is defined.
    # Without this guard, an empty header_image produces a directory URL that 404s.
    if header_image:
        header_bg = (
            f'<div class="header-bg" style="background-image: '
            f"url('static/images/characters/{character}/{header_image}');\"></div>"
        )
    else:
        header_bg = ""
    # Escape front-matter values that land in HTML text or attributes.
    # The article body (content_html) is already safe HTML from markdown.
    title_safe = html_lib.escape(title)
    title_jp_safe = html_lib.escape(title_jp)
    subtitle_safe = html_lib.escape(subtitle)

    # Optional in-game epithet shown above the title (e.g. "Onyx Line").
    epithet_html = (
        f'<div class="study-epithet">{html_lib.escape(epithet)}</div>'
        if epithet
        else ""
    )

    # Optional opening epigraph: the single heaviest quote, set before the body.
    if epigraph_jp or epigraph_en:
        epigraph_parts = ['<blockquote class="study-epigraph">']
        if epigraph_jp:
            epigraph_parts.append(
                f'<span class="epigraph-jp">{html_lib.escape(epigraph_jp)}</span>'
            )
        if epigraph_en:
            epigraph_parts.append(
                f'<em class="epigraph-en">{html_lib.escape(epigraph_en)}</em>'
            )
        epigraph_parts.append("</blockquote>")
        epigraph_html = "".join(epigraph_parts)
    else:
        epigraph_html = ""

    # Share-preview image (Open Graph / Twitter). Uses the header art.
    # Absolute when SITE_URL is set, since most scrapers require it.
    if header_image:
        img_path = f"static/images/characters/{character}/{header_image}"
        og_image = f"{SITE_URL.rstrip('/')}/{img_path}" if SITE_URL else img_path
    else:
        og_image = ""

    # Structured data so search engines treat each study as an Article.
    article_jsonld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "inLanguage": "en",
        "datePublished": date_str,
        "author": {"@type": "Person", "name": SITE_AUTHOR},
        "publisher": {"@type": "Organization", "name": SITE_TITLE},
        "wordCount": words,
    }
    if excerpt:
        article_jsonld["description"] = excerpt
    if og_image:
        article_jsonld["image"] = og_image
    canonical = page_url(f"{character}.html")
    if canonical:
        article_jsonld["mainEntityOfPage"] = canonical

    html = render_template(template, {
        "site_title": SITE_TITLE,
        "page_title": f"{title_safe} | {SITE_TITLE}",
        "seo_head": build_seo_head(f"{character}.html", article_jsonld),
        "character": character,
        "title": title_safe,
        "title_jp": title_jp_safe,
        "subtitle": subtitle_safe,
        "date": date_str,
        "reading_time": str(reading_min),
        "word_count": f"{words:,}",
        "content": content_html,
        "toc": toc_html,
        "mobile_toc": mobile_toc_html,
        "feedback": render_feedback(title_safe),
        "epithet": epithet_html,
        "epigraph": epigraph_html,
        "og_image": og_image,
        "header_bg": header_bg,
        "embers": embers_html,
        "progress_gem": progress_gem_html,
        "body_fx": body_fx,
        "site_author": SITE_AUTHOR,
        "year": str(datetime.now().year),
    })

    # Write output
    out_path = DIST_DIR / f"{character}.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  [OK] {md_path.name} -> {out_path.name} ({words:,} words, {reading_min} min)")

    return {
        "title": title,
        "title_jp": title_jp,
        "character": character,
        "excerpt": excerpt,
        "date": date_str,
        "reading_time": reading_min,
        "word_count": words,
        "url": f"{character}.html",
    }


# Inline script for the hero background: restores the last-compared mode,
# wires the toggle, and swaps a drift card to a new face on each full float
# cycle. Placeholders are filled by build_hero_assets. Kept inline so it needs
# no separate cache-busted asset.
_HERO_SCRIPT_TEMPLATE = """<script>
(function () {
  var DEFAULT_MODE = "__DEFAULT_MODE__";
  var SHOW_TOGGLE = __SHOW_TOGGLE__;
  var CARDS = __CARDS__;
  var body = document.body;
  var KEY = "umastudies-hero-mode";
  var VALID = { filmstrip: 1, drift: 1, off: 1 };

  // Drift is film-only on phones (it reads poorly on a narrow screen), so a
  // requested "drift" resolves to "filmstrip" while the mobile query matches.
  var mqMobile = window.matchMedia("(max-width: 640px)");
  var requested = DEFAULT_MODE;

  function effective(mode) {
    return (mqMobile.matches && mode === "drift") ? "filmstrip" : mode;
  }

  var MENU_LABELS = { filmstrip: "Film", drift: "Drift", off: "Off" };

  function applyMode(mode) {
    requested = mode;
    var eff = effective(mode);
    body.setAttribute("data-hero-mode", eff);
    if (SHOW_TOGGLE) {
      var items = document.querySelectorAll(".hero-menu-list button");
      for (var i = 0; i < items.length; i++) {
        items[i].setAttribute("aria-checked",
          items[i].getAttribute("data-mode") === eff ? "true" : "false");
      }
      var label = document.querySelector(".hero-menu-label");
      if (label) label.textContent = MENU_LABELS[eff] || eff;
    }
  }

  // Ignore a stale stored mode (e.g. a retired concept) so it cannot break the
  // hero; fall back to the default.
  var stored = null;
  try { stored = localStorage.getItem(KEY); } catch (e) {}
  if (!VALID[stored]) stored = null;
  applyMode(SHOW_TOGGLE && stored ? stored : DEFAULT_MODE);

  // Re-resolve when crossing the mobile breakpoint (rotate / resize).
  if (mqMobile.addEventListener) {
    mqMobile.addEventListener("change", function () { applyMode(requested); });
  }

  if (SHOW_TOGGLE) {
    var menu = document.querySelector(".hero-menu");
    if (menu) {
      var trigger = menu.querySelector(".hero-menu-trigger");
      var list = menu.querySelector(".hero-menu-list");
      function setOpen(open) {
        menu.setAttribute("data-open", open ? "true" : "false");
        trigger.setAttribute("aria-expanded", open ? "true" : "false");
      }
      trigger.addEventListener("click", function (e) {
        e.stopPropagation();
        setOpen(menu.getAttribute("data-open") !== "true");
      });
      list.addEventListener("click", function (e) {
        var b = e.target.closest("button");
        if (!b) return;
        var mode = b.getAttribute("data-mode");
        applyMode(mode);
        try { localStorage.setItem(KEY, mode); } catch (e2) {}
        setOpen(false);
      });
      document.addEventListener("click", function (e) {
        if (!menu.contains(e.target)) setOpen(false);
      });
      document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") setOpen(false);
      });
    }
  }

  // Drift: cards float in place. Each completed float cycle fades the card and
  // swaps in a new face (display:none halts the animation, so no swaps fire
  // while another mode is up). Hovering a card spins it and swaps its face at
  // the hidden mid-point of the turn.
  function randCard() { return CARDS[Math.floor(Math.random() * CARDS.length)]; }
  var cards = Array.prototype.slice.call(document.querySelectorAll(".drift-card"));

  Array.prototype.forEach.call(cards, function (card) {
    var img = card.querySelector("img");
    if (!img) return;

    card.addEventListener("animationiteration", function () {
      if (card.classList.contains("is-spinning")) return;
      img.style.opacity = "0";
      setTimeout(function () { img.src = randCard(); img.style.opacity = ""; }, 650);
    });

    card.addEventListener("mouseenter", function () {
      if (card.classList.contains("is-spinning")) return;
      card.classList.add("is-spinning");
      setTimeout(function () { img.src = randCard(); }, 450); // swap while edge-on
      setTimeout(function () { card.classList.remove("is-spinning"); }, 900);
    });
  });
})();
</script>"""


def build_hero_assets() -> dict:
    """Build the landing-page hero background (film strip and drift field).

    Reads optimized card webps from HERO_CARDS_DIR and returns the stage markup,
    the body data attribute carrying the default mode, and the inline script.
    Returns empty strings when there are no cards or the feature is fully off.
    Uses a fixed RNG seed so repeated builds are byte-stable (no git churn).
    """
    import random

    cards_dir = STATIC_DIR / "images" / "hero-cards"
    card_files = (
        sorted(p.name for p in cards_dir.glob("*.webp")) if cards_dir.exists() else []
    )

    feature_on = bool(card_files) and (HERO_MODE != "off" or HERO_SHOW_TOGGLE)
    if not feature_on:
        return {"hero_body_attr": "", "hero_stage": "", "hero_menu": "", "hero_script": ""}

    rel = [f"{HERO_CARDS_DIR}/{name}" for name in card_files]
    rng = random.Random(42)

    # Film strip: HERO_ROWS rows, alternating scroll direction, each a shuffled
    # ordering of the full set duplicated so the CSS translate loop is seamless.
    # A frame that fails to load removes itself so the strip does not gap-stall.
    rows_html = []
    for i in range(HERO_ROWS):
        order = rel[:]
        rng.shuffle(order)
        frames = "".join(
            f'<div class="film-frame"><img src="{src}" alt="" loading="lazy" '
            "decoding=\"async\" onerror=\"this.closest('.film-frame').remove()\">"
            "</div>"
            for src in order
        )
        direction = "reverse" if i % 2 else "normal"
        # Duration scales with the card count so the on-screen scroll SPEED
        # (pixels/second) stays constant as cards are added: the track grows
        # longer, so the time to cross it must grow with it. 32 is the count the
        # 88s/16s timing was tuned at. Lower rows are slower for parallax.
        dur = round((len(rel) / 32) * (88 + i * 16), 1)
        rows_html.append(
            f'<div class="filmstrip-row" style="--film-dur:{dur}s;'
            f'--film-dir:{direction}">'
            f'<div class="filmstrip-track">{frames}{frames}</div></div>'
        )
    filmstrip_html = f'<div class="filmstrip-layer">{"".join(rows_html)}</div>'

    # Drift field: a jittered grid so cards spread evenly instead of clumping,
    # then float. left/top are the card CENTER (the CSS keyframe translates
    # -50%,-50%). Placed server-side so a no-JS visitor still sees a static field.
    #
    # Positions use a DEDICATED rng, decoupled from the film strip AND the card
    # count, so adding cards never shifts the drift layout again. shuffle()
    # consumption depends only on list LENGTH, so replaying the tuning-time
    # consumption (Random(42), then HERO_ROWS strip shuffles plus one pool
    # shuffle, all at the count the layout was approved under) reproduces the
    # exact approved positions and freezes them. Which faces appear uses a
    # separate rng, so it can still draw from the full, growing pool.
    n_drift = min(HERO_DRIFT_COUNT, len(rel))
    cols = 4 if n_drift >= 7 else 3
    rows = math.ceil(n_drift / cols)
    cell_w = 100 / cols
    cell_h = 100 / rows

    DRIFT_TUNED_COUNT = 32
    pos_rng = random.Random(42)
    _warm = list(range(DRIFT_TUNED_COUNT))
    for _ in range(HERO_ROWS + 1):
        pos_rng.shuffle(_warm)

    pick_rng = random.Random(99)
    drift_pool = rel[:]
    pick_rng.shuffle(drift_pool)

    drift_cards = []
    for i in range(n_drift):
        src = drift_pool[i]
        col = i % cols
        row = i // cols
        left = (col + 0.5) * cell_w + pos_rng.uniform(-cell_w * 0.24, cell_w * 0.24)
        top = (row + 0.5) * cell_h + pos_rng.uniform(-cell_h * 0.24, cell_h * 0.24)
        left = max(8, min(92, left))
        # top floor keeps the tallest card clear of the header at the stage top
        top = max(18, min(86, top))
        tilt = pos_rng.uniform(-11, 11)
        dur = pos_rng.uniform(24, 40)  # slow, dreamlike
        delay = pos_rng.uniform(-40, 0)  # negative desyncs the starting phase
        width = pos_rng.uniform(118, 168)
        opacity = pos_rng.uniform(0.74, 1.0)  # depth: some windows farther away
        drift_cards.append(
            f'<div class="drift-card" style="left:{left:.1f}%;top:{top:.1f}%;'
            f'--tilt:{tilt:.1f}deg;--drift-dur:{dur:.1f}s;'
            f'--drift-delay:{delay:.1f}s;--drift-op:{opacity:.2f};'
            f'width:{width:.0f}px">'
            f'<img src="{src}" alt="" loading="lazy" decoding="async" '
            "onerror=\"this.closest('.drift-card').remove()\"></div>"
        )
    drift_html = f'<div class="drift-layer">{"".join(drift_cards)}</div>'

    stage = (
        '<div class="hero-stage" aria-hidden="true">'
        + filmstrip_html
        + drift_html
        + '<div class="hero-scrim"></div>'
        + "</div>"
    )

    # Mode control: a small dropdown that lives in the top nav (see the
    # {{hero_menu}} slot in index.html). This is the prototype/kill-switch
    # control; drop it for production by setting HERO_SHOW_TOGGLE = False.
    menu = ""
    if HERO_SHOW_TOGGLE:
        modes = (("filmstrip", "Film"), ("drift", "Drift"), ("off", "Off"))
        items = "".join(
            f'<button type="button" role="menuitemradio" data-mode="{m}">{label}</button>'
            for m, label in modes
        )
        current_label = dict(modes).get(HERO_MODE, "Film")
        menu = (
            '<div class="hero-menu" data-open="false">'
            '<button type="button" class="hero-menu-trigger" '
            'aria-haspopup="true" aria-expanded="false">'
            '<span class="hero-menu-eyebrow">Hero</span>'
            f'<span class="hero-menu-label">{current_label}</span>'
            '<span class="hero-menu-caret" aria-hidden="true">&#9662;</span>'
            "</button>"
            f'<div class="hero-menu-list" role="menu">{items}</div>'
            "</div>"
        )

    script = (
        _HERO_SCRIPT_TEMPLATE.replace("__DEFAULT_MODE__", HERO_MODE)
        .replace("__SHOW_TOGGLE__", "true" if HERO_SHOW_TOGGLE else "false")
        .replace("__CARDS__", json.dumps(rel))
    )

    return {
        "hero_body_attr": f' data-hero-mode="{HERO_MODE}"',
        "hero_stage": stage,
        "hero_menu": menu,
        "hero_script": script,
    }


def build_index(studies: list[dict]) -> None:
    """Build the index page listing all studies."""
    # Sort by date descending
    studies.sort(key=lambda s: s["date"], reverse=True)

    # Build study cards HTML
    cards_html = []
    for study in studies:
        # Escape text fields so a stray <, &, or {{ in front matter cannot
        # break the markup or collide with the {{placeholder}} pass.
        card_title = html_lib.escape(study["title"])
        card_title_jp = html_lib.escape(study["title_jp"])
        card_excerpt = html_lib.escape(study["excerpt"])
        card_url = html_lib.escape(study["url"], quote=True)

        # Optional per-character card art. Auto-included when a card_art.webp
        # exists in the character's image folder; cards without one render
        # text-only. Cropped/anchored via the .study-card.has-art CSS.
        character = study["character"]
        art_rel = f"static/images/characters/{character}/card_art.webp"
        has_art = (STATIC_DIR / "images" / "characters" / character / "card_art.webp").exists()
        if has_art:
            art_alt = html_lib.escape(study["title"], quote=True)
            art_html = (
                f'\n      <img class="card-art" src="{art_rel}" alt="{art_alt}"'
                ' loading="lazy" decoding="async" aria-hidden="true">'
            )
            card_class = "study-card has-art fade-in-up"
        else:
            art_html = ""
            card_class = "study-card fade-in-up"

        card = f"""
    <a href="{card_url}" class="{card_class}"
       style="--card-accent: var(--accent-primary)">{art_html}
      <div class="card-body">
        <div class="card-character">{card_title}</div>
        <div class="card-character-jp">{card_title_jp}</div>
        <div class="card-excerpt">{card_excerpt}</div>
        <div class="card-meta">
          <span>{study['date']}</span>
          <span class="card-meta-divider"></span>
          <span>{study['word_count']:,} words</span>
          <span class="card-meta-divider"></span>
          <span>{study['reading_time']} min read</span>
        </div>
      </div>
    </a>"""
        cards_html.append(card)

    # "Coming soon" section, rendered only when PLANNED_STUDIES is populated.
    if PLANNED_STUDIES:
        planned_cards = []
        for planned in PLANNED_STUDIES:
            note = planned.get("note", "")
            planned_cards.append(
                '<div class="planned-card">'
                f'<div class="card-character">{html_lib.escape(planned.get("name", ""))}</div>'
                f'<div class="card-character-jp">{html_lib.escape(planned.get("name_jp", ""))}</div>'
                + (f'<div class="card-excerpt">{html_lib.escape(note)}</div>' if note else "")
                + "</div>"
            )
        planned_html = (
            '<section class="planned"><h2>Coming soon</h2>'
            '<div class="planned-grid">' + "".join(planned_cards) + "</div></section>"
        )
    else:
        planned_html = ""

    template = load_template("index.html")
    context = {
        "site_title": SITE_TITLE,
        "seo_head": build_seo_head(""),
        "site_title_jp": SITE_TITLE_JP,
        "site_description": SITE_DESCRIPTION,
        "study_cards": "\n".join(cards_html),
        "planned": planned_html,
        "study_count": str(len(studies)),
        "site_author": SITE_AUTHOR,
        "year": str(datetime.now().year),
    }
    context.update(build_hero_assets())
    html = render_template(template, context)

    out_path = DIST_DIR / "index.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  [OK] index.html ({len(studies)} studies)")


def build_feed(studies: list[dict]) -> None:
    """Write an RSS 2.0 feed at dist/feed.xml. Expects studies newest-first.

    Links are absolute only when SITE_URL is set; until then the feed exists
    but its links are relative (not valid for most RSS readers).
    """
    base = SITE_URL.rstrip("/")
    items = []
    for study in studies:
        link = f"{base}/{study['url']}" if base else study["url"]
        try:
            dt = datetime.strptime(study["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            pub_line = f"      <pubDate>{format_datetime(dt)}</pubDate>\n"
        except ValueError:
            pub_line = ""
        items.append(
            "    <item>\n"
            f"      <title>{html_lib.escape(study['title'])}</title>\n"
            f"      <link>{html_lib.escape(link)}</link>\n"
            f"      <guid isPermaLink=\"false\">{html_lib.escape(link)}</guid>\n"
            f"{pub_line}"
            f"      <description>{html_lib.escape(study['excerpt'])}</description>\n"
            "    </item>"
        )

    feed = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0">\n'
        "  <channel>\n"
        f"    <title>{html_lib.escape(SITE_TITLE)}</title>\n"
        f"    <link>{html_lib.escape(base)}</link>\n"
        f"    <description>{html_lib.escape(SITE_DESCRIPTION)}</description>\n"
        + "\n".join(items)
        + ("\n" if items else "")
        + "  </channel>\n"
        "</rss>\n"
    )

    with open(DIST_DIR / "feed.xml", "w", encoding="utf-8") as f:
        f.write(feed)
    note = "" if base else "  (set SITE_URL for valid links)"
    print(f"  [OK] feed.xml ({len(studies)} items){note}")


def build_robots() -> None:
    """Write dist/robots.txt. Allows all crawlers and points at the sitemap.

    The Sitemap line is only emitted when SITE_URL is set, since it must be an
    absolute URL.
    """
    lines = ["User-agent: *", "Allow: /"]
    sitemap_url = page_url("sitemap.xml")
    if sitemap_url:
        lines.append("")
        lines.append(f"Sitemap: {sitemap_url}")
    with open(DIST_DIR / "robots.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("  [OK] robots.txt")


def build_sitemap(studies: list[dict]) -> None:
    """Write dist/sitemap.xml listing the home, about, and every study.

    Requires SITE_URL (sitemap locs must be absolute). Skipped with a warning
    otherwise. lastmod uses each study's front-matter date; the home uses the
    newest study date.
    """
    base = SITE_URL.rstrip("/")
    if not base:
        print("  [skip] sitemap.xml (SITE_URL unset)")
        return

    def url_entry(loc: str, lastmod: str = "") -> str:
        mod = f"    <lastmod>{lastmod}</lastmod>\n" if lastmod else ""
        return f"  <url>\n    <loc>{html_lib.escape(loc)}</loc>\n{mod}  </url>"

    entries = []
    newest = max((s["date"] for s in studies), default="")
    entries.append(url_entry(page_url(""), newest))
    if (CONTENT_DIR.parent / "about.md").exists():
        entries.append(url_entry(page_url("about.html")))
    for study in studies:
        entries.append(url_entry(page_url(study["url"]), study["date"]))

    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
    )
    with open(DIST_DIR / "sitemap.xml", "w", encoding="utf-8") as f:
        f.write(sitemap)
    print(f"  [OK] sitemap.xml ({len(entries)} urls)")


def build_about() -> None:
    """Build the About page from content/about.md, if it exists."""
    about_path = CONTENT_DIR.parent / "about.md"
    if not about_path.exists():
        return
    with open(about_path, "r", encoding="utf-8") as f:
        raw = f.read()

    _, body = parse_front_matter(raw)
    md_converter = markdown.Markdown(extensions=MD_EXTENSIONS)
    content_html = add_heading_ids(md_converter.convert(body))

    template = load_template("about.html")
    rendered = render_template(template, {
        "site_title": SITE_TITLE,
        "page_title": f"About | {SITE_TITLE}",
        "seo_head": build_seo_head("about.html"),
        "content": content_html,
        "site_author": SITE_AUTHOR,
        "year": str(datetime.now().year),
    })

    out_path = DIST_DIR / "about.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(rendered)
    print("  [OK] about.html")


def copy_static() -> None:
    """Copy static assets to dist."""
    import shutil
    dest = DIST_DIR / "static"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(STATIC_DIR, dest)
    print(f"  [OK] static/ -> dist/static/")


def main():
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"UmaStudies Build\n{'=' * 40}\n")

    # Copy static files
    copy_static()

    # Find and build all studies
    study_files = sorted(CONTENT_DIR.glob("*.md"))
    if not study_files:
        print("  No study files found in content/studies/")
        print("  Creating index with no studies...\n")

    studies = []
    for md_path in study_files:
        try:
            info = build_study(md_path)
            studies.append(info)
        except Exception as e:
            print(f"  [FAIL] {md_path.name}: {e}")

    # Build index, about page, RSS feed, and SEO files
    build_index(studies)
    build_about()
    build_feed(studies)
    build_robots()
    build_sitemap(studies)

    print(f"\n{'=' * 40}")
    print(f"Build complete. Output: {DIST_DIR}")
    print(f"Studies built: {len(studies)}")


if __name__ == "__main__":
    main()
