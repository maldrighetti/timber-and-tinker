# Timber & Tinker

Wood projects for kids and families, inspired by Leonardo da Vinci, with a drawing for every step. The site is there to get kids outdoors, teach real building skills, and make time to build together.

**Site:** https://maldrighetti.github.io/timber-and-tinker/
**Repository:** https://github.com/maldrighetti/timber-and-tinker

The pages are plain HTML. A small Python script builds them from the project folders. There is no database, no analytics, and no cookies.

## How the site is organized

- `projects/` — one folder per project. Each folder has `PROJECT.md` (the instructions), the PNG drawings that file names, and an optional `project.json`.
- `content/DISCLAIMER.md` — the “Before you build” page. Shown as written. Do not rewrite it.
- `content/about.md` — the About page.
- `build.py` — builds the site into `_site/`.
- `src/` — the shared stylesheet, the small script that enlarges a drawing, and the icon.
- `site.json` — the site name, the repository URL, and the optional custom domain.
- `.github/workflows/pages.yml` — builds the site and publishes it to GitHub Pages on every push to `main`.

The built site has a home page (one card per project), a page per project, “Before you build,” and About. Every page links to “Before you build” in the footer. Each project page also points to it near the top.

Links in the built HTML are relative. They work under `/timber-and-tinker/` on GitHub Pages, and they keep working if the site later moves to the root of a domain.

## Add a project

1. Create a folder, for example `projects/bird-feeder/`. Use lowercase words and hyphens.
2. Add `PROJECT.md` and the PNG drawings it names. Keep the same shape as the projects already here: a title and tagline, ages, time, difficulty, safety, parts, a cut list, tools, numbered steps, why it works, and what to try next.
3. Name drawings in the instructions so the build can place them:
   - `![A short description](01-step.png)` shows that drawing. The description in the brackets is the alt text, and it is also the caption when it says more than the step heading.
   - A line that only names files, such as `` `02-step.png` `` or `` `02-step.png` · `02-step-side.png` ``, shows those drawings under the current step. The step heading becomes the alt text.
   - A filename mentioned inside a sentence, such as “see `` `02-step.png` ``,” stays as text.
4. Optionally add `project.json`:

```json
{
  "order": 4,
  "video": "",
  "parts": [
    { "name": "1x2 pine board", "url": "", "note": "" }
  ]
}
```

- `order` sets the order inside a section. Lower numbers come first. If you omit it, the project is listed after the numbered ones.
- `section` is optional. Leave it out, or set `"kids"`, and the project stays in the Projects list. `"home-prep"` puts it under Home & Prep. A new section needs a heading and a one-line intro in the `SECTIONS` dict in `build.py`.
- `video` is a YouTube link, a youtu.be link, or an 11-character video id. Leave it as `""` and the “Watch the build” slot stays hidden. When it is set, the page embeds the video from the privacy-enhanced YouTube player (`youtube-nocookie.com`), just before the assembly steps.
- `parts` is a list of things a family might buy. `name` is required. `url` is a normal `https://` link, or `""` if you do not have one yet. `note` is optional.
- The “Get the parts” box is hidden until at least one part has a `url`. The affiliate-disclosure line is shown only then, under that box.

5. Open a pull request. When it is merged into `main`, the Pages workflow publishes the update.

The build fails if `PROJECT.md` names a PNG that is not in the folder.

## Preview locally

```bash
python3 -m pip install -r requirements.txt
python3 build.py
mkdir -p /tmp/tat-preview
ln -sfn "$(pwd)/_site" /tmp/tat-preview/timber-and-tinker
python3 -m http.server 8080 --directory /tmp/tat-preview
```

Open http://localhost:8080/timber-and-tinker/

To preview the way a custom domain would serve the site (at `/` instead of `/timber-and-tinker/`), run `python3 -m http.server 8080 --directory _site` instead.

## Custom domain later

`site.json` has `"customDomain": ""`. Leave that empty until the domain is ready. When `timberandtinker.org` is purchased and DNS is pointed at GitHub Pages:

1. Set `"customDomain": "timberandtinker.org"` in `site.json`.
2. Merge the change. The build writes a `CNAME` file into the published site. Do not add that file before DNS works, or GitHub Pages can stop serving the `github.io` address.
3. In the repository, open Settings → Pages → Custom domain and confirm `timberandtinker.org`.

No link changes are required. The pages already use relative URLs.

## GitHub Pages

Pages should use **GitHub Actions** as the source (Settings → Pages → Build and deployment → Source). The workflow in `.github/workflows/pages.yml` builds `_site/` and deploys it. It also builds on pull requests, without deploying, so a broken project folder fails the check before it is merged.

## Licenses

- Site code (the build script, styles, script, and workflow) is [MIT](LICENSE). Copyright 2026 Michael Aldrighetti.
- Instructions and drawings are [CC BY-NC 4.0](LICENSE-CONTENT.md). Copyright 2026 Michael Aldrighetti.

No analytics, ads, or cookies.
