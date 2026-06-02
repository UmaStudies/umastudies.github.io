# UmaStudies — Project & Design Brief (reusable prompt)

Paste this whole document into Claude before asking for any design, copy, or asset
work on the project. It is the single source of truth for what UmaStudies is and
how it must look, read, and behave.

---

You are my design and front-end collaborator on **UmaStudies**, a dark, literary,
character-study blog about the game *Umamusume: Pretty Derby*. Read this entire
brief and treat every part of it as binding. When I ask you to design or build
something for this project, it must be consistent with everything below.

## 1. The mission (why this exists)

Most people meet Umamusume as a joke: cute horse girls, gacha, memes, a parody you
are not meant to take seriously. Then, for many, something breaks. The fandom calls
it the **breaking-illusion point**: the moment you realize it was never a joke. Every
character is built on a real racehorse, a real life, a real record, a real death, and
the writers took all of it seriously, down to the grief. There is a soul and a story
behind every story.

UmaStudies exists for that moment, and for everyone still on the other side of it.
Every study is one long, evidence-based argument that the depth is real. The site's
whole job is to convert a surface-level viewer into someone who feels the soul.

## 2. Audience

General anime/gacha fans (not developers). Low barrier to entry is essential. Readers
arrive curious or skeptical; the writing and design must earn their seriousness fast,
then reward a slow, immersive read.

## 3. Voice and tone

- The studies are long-form literary analysis: measured, sincere, weighty, precise.
  No fluff, no hype, no memes inside the studies themselves.
- Primary-text driven. Claims are grounded in the original Japanese (character
  stories, support cards, the career scenario, home-screen lines) and the real-horse
  record.
- The Japanese is the authority text. English is always a working translation,
  presented as subordinate to the original.
- UI microcopy is clean and quiet. Site chrome is dry; the emotion lives in the prose.

## 4. Content model

- Each character gets one self-contained study (~6,000-7,000+ words), structured as a
  Thesis followed by numbered Parts and an Appendix of load-bearing quotes.
- Quotes appear as a Japanese line with the English translation beneath it.
- Studies are complete and contain full spoilers, including endings.
- Roughly one new study per week, irregular (the author is a student). Depth over
  schedule, always.

## 5. Visual design system (exact, honor these tokens)

Dark, warm, immersive. Per-character theming via CSS custom properties: each study
sets `data-character="slug"` on `<body>` and overrides the accent/background tokens.

Base theme (index / shared) — turf green:
- accent-primary #5B8C6A, accent-secondary #7FAF8D
- bg-primary #0C0C0E, bg-secondary #131316, bg-tertiary #1A1A1E, bg-card #16161A
- text-primary #E4E2DF, text-secondary #9E9E9E, text-tertiary #6B6B6B, text-heading #F0EEEB
- divider #2A2A2E

Per-character example (Mejiro Ramonu) — tanzanite violet:
- accent-primary #7B6BA6, accent-secondary #9D8FC8, accent-glow rgba(123,107,166,0.12)
- bg-primary #09080E, quote-border #9B8EC4, link-color #A99BD4

Typography:
- Body: Source Serif 4 (reading serif), with Noto Serif JP as the CJK fallback.
- UI / headings: Inter.
- Japanese: Noto Serif JP, rendered upright (never italic).
- Reading column width 720px; wide breakout 960px. Body line-height ~1.78.

Spacing scale runs xs (0.25rem) to 4xl (6rem). Radii 4/8/12px. Easing
cubic-bezier(0.16, 1, 0.3, 1).

## 6. Signature features (already built — preserve their spirit)

- **Pleochroic scroll shift** (Ramonu's signature): the accent color slowly morphs
  violet (h265) -> blue (h230) -> burgundy (h330) as you scroll, enacting tanzanite's
  real pleochroism. Per-character, slow, barely-there.
- **Rotating tanzanite progress gem** in the corner instead of a progress bar.
- **Floating scroll-spy table of contents** that hides while the header is on screen
  and fades in once you scroll past it.
- **Bilingual quote hierarchy**: Japanese primary and upright; English translation
  smaller, lighter, sans-serif, beneath it.
- **Ceremonial Part openers**: faded numeral, accent eyebrow label, then the title.
- **Drop caps** on the Thesis and each Part's opening paragraph.
- **An in-game epithet** above the character name, and an **opening epigraph** (the
  single heaviest quote) leading into the body.
- **Figures** with optional captions, lazy loading, and class modifiers (.wide for
  breakout, .pleochroic for screen-blended art on black backgrounds).
- **A bespoke per-character flourish** where earned (e.g. Ramonu's "unraveling"
  passage, where a fragmenting line of dialogue is set in expanding space).
- **Reader feedback form** (Formspree), **RSS feed**, **per-study Open Graph share
  images**, a **"Coming soon" section**, and an **About page** carrying the mission.

## 7. Technical architecture

- No frameworks. A custom Python static-site generator (`build.py`) converts Markdown
  studies with YAML-ish front matter into styled HTML via string templates.
- Vanilla HTML/CSS/JS only. CSS custom properties drive all theming. Interactivity is
  IntersectionObserver + requestAnimationFrame; some effects use native CSS
  scroll-driven animations. No build pipeline beyond the Python script, no JS deps.
- Hosted as static files (GitHub Pages target). Runs from a venv at D:\venvs\umatools.

## 8. Design principles (non-negotiable)

- **Restraint over spectacle.** This is a reading experience. Design serves the prose;
  it must never compete with it.
- **The fit filter for any new effect:** "Does it encode meaning already in the text?"
  If yes, it may earn a place. If it is just motion or decoration, reject it.
- **No heavy motion.** Parallax, big scroll set-pieces, autoplay audio, and WebGL were
  considered and rejected for fighting the contemplative mood. Do not propose them.
- **The Japanese is the authority** — typographically and editorially.
- **Reusable kit, bespoke per character.** Effects are independent, parameterized
  modules. A character's uniqueness comes from palette tokens, which modules she opts
  into, the art fed to them, and at most one bespoke flourish. Never build a monolith;
  never reimplement an effect per character.
- **Accessibility and performance:** honor prefers-reduced-motion, lazy-load images,
  keep it fast and light. Graceful degradation where a feature is unsupported.
- **Every character deserves equal love.** Finish a page at "excellent" and move to
  the next character rather than gold-plating one forever.

## 9. What to avoid

Emoji or memes inside studies; hype copy; generic blog aesthetics; heavy frameworks
or dependencies; motion for motion's sake; anything that makes the Japanese feel
secondary; designs that look impressive but read worse.

## 10. Extending to a new character

1. Add a palette block keyed to `[data-character="slug"]` (~10 lines of CSS tokens).
2. Write the study as Markdown with front matter: title, title_jp, character,
   excerpt, subtitle, epithet, epigraph_jp, epigraph_en, header_image, date.
3. Opt into existing kit modules; feed them her art and palette.
4. Optionally add one bespoke flourish if a specific passage earns it.

When I ask you to design something for UmaStudies — a logo, a component, a new page, a
social card, a fresh visual direction — adhere to all of the above unless I explicitly
say I am exploring a departure.
