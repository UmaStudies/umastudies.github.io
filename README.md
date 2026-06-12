# UmaStudies

In-depth, primary-text character studies of the cast of *Umamusume: Pretty
Derby*. Built from the original Japanese (character stories, support cards, the
career scenario, home-screen lines) alongside the real-horse record behind each
character. The Japanese is treated as the authority text; the English is a
working translation.

Live site: https://umastudies.github.io/

## How it works

A small custom static-site generator. No frameworks. Each study is a Markdown
file with YAML-style front matter; `build.py` renders them into static HTML
using string-replacement templates, then writes `robots.txt`, `sitemap.xml`,
and an RSS feed.

```
site/
  build.py            generator
  content/
    about.md          about page
    studies/          one Markdown file per character study
  templates/          HTML templates with {{placeholder}} slots
  static/             CSS, JS, images, favicon
  dist/               build output (gitignored, regenerated)
```

## Build

Requires Python with the `markdown` package (see `requirements.txt`).

```sh
python site/build.py
```

Output lands in `site/dist/`. Deployment to GitHub Pages is handled by the
workflow in `.github/workflows/`.

## License

This repository is dual-licensed because it contains two different kinds of
work:

- **Code** (the generator, templates, stylesheets, scripts) is licensed under
  the **MIT License**. See [`LICENSE`](LICENSE).
- **Written content** (the character studies and editorial prose under
  `site/content/`) is licensed under **CC BY-NC-ND 4.0**. See
  [`LICENSE-CONTENT.md`](LICENSE-CONTENT.md).

*Umamusume: Pretty Derby* and all related characters and artwork belong to
Cygames, Inc. This is an unofficial, non-commercial fan project.
