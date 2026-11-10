#!/usr/bin/env python3
"""Build the Timber & Tinker static site.

Reads projects/*/PROJECT.md (and optional project.json) plus content/*.md
and writes HTML to _site/. Links are relative, so the same files work at
https://maldrighetti.github.io/timber-and-tinker/ and, later, at a custom domain.
"""

from __future__ import annotations

import html
import json
import re
import shutil
import sys
from pathlib import Path

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "_site"
PROJECTS = ROOT / "projects"
CONTENT = ROOT / "content"
SRC = ROOT / "src"

PNG_NAME = re.compile(r"^[\w.-]+\.png$")
SEPARATOR = re.compile(r"^[\s·•|/,–—-]*$")
YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
HEADING_OR_P = re.compile(r"<h([1-6])\b[^>]*>(.*?)</h\1>|<p>(.*?)</p>", re.S)
IMG_OR_CODE = re.compile(r"<img\b([^>]*?)/?>|<code>([^<]*)</code>", re.I)
ATTRS = re.compile(r'([\w:-]+)\s*=\s*"([^"]*)"')
TABLE = re.compile(r"<table\b[^>]*>.*?</table>", re.S)
THEAD = re.compile(r"<thead>.*?</thead>", re.S)
TAG = re.compile(r"<[^>]+>")

MD = (
    MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False})
    .enable("table")
)

# A new home-page section needs a heading and a one-line intro here.
# Projects with no section, or with section "kids", stay in the first list.
SECTIONS = {
    "kids": {
        "heading": "Projects",
        "id": "projects",
        "intro": "",
        "nav": False,
    },
    "home-prep": {
        "heading": "Home & Prep",
        "id": "home-prep",
        "intro": "Practical builds for the shop, the yard, and a power outage, all made with a handsaw, a drill, and basic tools.",
        "nav": True,
    },
}

LIGHTBOX = """
<dialog class="lightbox" id="lightbox" aria-label="Enlarged drawing">
  <div class="lightbox-bar">
    <button type="button" class="lightbox-close">Close</button>
    <button type="button" class="lightbox-fit">Actual size</button>
  </div>
  <div class="lightbox-scroll">
    <img alt="">
  </div>
</dialog>
"""


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def strip_tags(text: str) -> str:
    return html.unescape(TAG.sub("", text))


def slugify(text: str) -> str:
    text = text.lower().replace("'", "").replace("’", "").replace("‘", "")
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "section"


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        if handle.read(8) != b"\x89PNG\r\n\x1a\n":
            raise SystemExit(f"Not a PNG: {path}")
        handle.read(4)
        if handle.read(4) != b"IHDR":
            raise SystemExit(f"PNG has no IHDR: {path}")
        data = handle.read(8)
    return int.from_bytes(data[:4], "big"), int.from_bytes(data[4:], "big")


def youtube_id(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if YOUTUBE_ID.fullmatch(value):
        return value
    match = re.search(
        r"(?:youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/|youtube\.com/watch\?v=)([A-Za-z0-9_-]{11})",
        value,
    )
    if not match:
        raise SystemExit(f"Unrecognized YouTube value: {value!r}")
    return match.group(1)


def parse_attrs(raw: str) -> dict[str, str]:
    return {key: html.unescape(val) for key, val in ATTRS.findall(raw)}


def alt_from_heading(heading: str) -> str:
    cleaned = re.sub(r"^\d+\.\s*", "", heading).strip()
    return cleaned or heading or "Drawing"


def caption_worth_showing(alt: str, heading: str) -> bool:
    def norm(value: str) -> str:
        return re.sub(r"^\d+\.\s*", "", value).strip().lower()

    left = norm(alt)
    right = norm(heading)
    if not left or left == right:
        return False
    if right and left.startswith(right):
        return False
    return True


def drawing_figure(src: str, alt: str, sizes: dict[str, tuple[int, int]], first: bool, caption: bool) -> str:
    width, height = sizes.get(src, (0, 0))
    dims = f' width="{width}" height="{height}"' if width and height else ""
    loading = "eager" if first else "lazy"
    priority = ' fetchpriority="high"' if first else ""
    cap = f'<figcaption aria-hidden="true">{esc(alt)}</figcaption>' if caption else ""
    return (
        '<figure class="drawing">'
        f'<a class="drawing-link" href="{esc(src)}">'
        f'<img src="{esc(src)}" alt="{esc(alt)}"{dims} loading="{loading}" decoding="async"{priority}>'
        '<span class="visually-hidden"> Enlarge</span>'
        "</a>"
        f"{cap}</figure>"
    )


def is_drawing_paragraph(inner: str) -> bool:
    if ".png" not in inner:
        return False
    stripped = re.sub(r"<img\b[^>]*?/?>", "", inner, flags=re.I)
    stripped = re.sub(r"<code>\s*[\w.-]+\.png\s*</code>", "", stripped)
    stripped = strip_tags(stripped)
    return bool(SEPARATOR.fullmatch(stripped))


def render_drawing_paragraph(inner: str, heading: str, sizes: dict[str, tuple[int, int]], first: bool) -> tuple[str, bool]:
    figures: list[str] = []
    seen: list[str] = []
    generated_index = 0
    for match in IMG_OR_CODE.finditer(inner):
        if match.group(1) is not None:
            attrs = parse_attrs(match.group(1))
            src = attrs.get("src", "")
            alt = attrs.get("alt") or alt_from_heading(heading)
            explicit = bool(attrs.get("alt"))
            seen.append(src)
        else:
            src = match.group(2).strip()
            if not PNG_NAME.fullmatch(src) or src in seen:
                continue
            alt = alt_from_heading(heading)
            if generated_index:
                alt = f"{alt}, drawing {generated_index + 1}"
            generated_index += 1
            explicit = False
            seen.append(src)
        if not src:
            continue
        figures.append(
            drawing_figure(src, alt, sizes, first and not figures, caption_worth_showing(alt, heading) and explicit)
        )
    if figures and first:
        first = False
    return "\n".join(figures), first


def transform_html(source_html: str, sizes: dict[str, tuple[int, int]]) -> str:
    """Turn picture references into large figures and give headings ids."""
    out: list[str] = []
    position = 0
    heading = ""
    used_ids: set[str] = set()
    first_image = True
    for match in HEADING_OR_P.finditer(source_html):
        out.append(source_html[position:match.start()])
        if match.group(1):
            level = match.group(1)
            inner = match.group(2)
            heading = strip_tags(inner).strip()
            base = slugify(heading)
            slug = base
            number = 2
            while slug in used_ids:
                slug = f"{base}-{number}"
                number += 1
            used_ids.add(slug)
            out.append(f'<h{level} id="{slug}">{inner}</h{level}>')
        else:
            inner = match.group(3)
            if is_drawing_paragraph(inner):
                figures, first_image = render_drawing_paragraph(inner, heading, sizes, first_image)
                out.append(figures)
            elif "<strong>Ages:</strong>" in inner and "Time to build" in inner:
                out.append(f'<p class="facts">{inner.replace(chr(10), "<br>\n")}</p>')
            elif re.fullmatch(r"\s*<strong>[^<]+</strong>\s*", inner):
                out.append(f'<p class="subhead">{inner.strip()}</p>')
            elif re.match(r"\s*<strong>\s*Look for:", inner):
                out.append(f'<p class="look-for">{inner}</p>')
            else:
                out.append(f"<p>{inner}</p>")
        position = match.end()
    out.append(source_html[position:])
    html_out = "".join(out)
    return TABLE.sub(wrap_table, html_out)


def wrap_table(match: re.Match[str]) -> str:
    table = match.group(0)

    def drop_empty_head(head: re.Match[str]) -> str:
        if strip_tags(head.group(0)).strip():
            return head.group(0)
        return ""

    table = THEAD.sub(drop_empty_head, table)
    return f'<div class="table-wrap" tabindex="0">{table}</div>'


def render_markdown(text: str, sizes: dict[str, tuple[int, int]]) -> str:
    return transform_html(MD.render(text), sizes)


def load_project_meta(folder: Path) -> dict:
    path = folder / "project.json"
    meta = {"order": 1000, "video": "", "parts": [], "section": "kids"}
    if not path.exists():
        return meta
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must be a JSON object")
    if "order" in data:
        if not isinstance(data["order"], int):
            raise SystemExit(f"{path}: order must be a whole number")
        meta["order"] = data["order"]
    if "section" in data and data["section"] not in (None, ""):
        if not isinstance(data["section"], str):
            raise SystemExit(f"{path}: section must be a string")
        section = data["section"].strip()
        if section not in SECTIONS:
            known = ", ".join(SECTIONS)
            raise SystemExit(f"{path}: unknown section {section!r}. Known sections: {known}.")
        meta["section"] = section
    if "video" in data and data["video"] is not None:
        if not isinstance(data["video"], str):
            raise SystemExit(f"{path}: video must be a string")
        meta["video"] = data["video"].strip()
    parts = data.get("parts", [])
    if not isinstance(parts, list):
        raise SystemExit(f"{path}: parts must be a list")
    cleaned = []
    for index, part in enumerate(parts, start=1):
        if not isinstance(part, dict):
            raise SystemExit(f"{path}: parts[{index}] must be an object")
        name = part.get("name", "")
        url = part.get("url", "")
        note = part.get("note", "")
        if not isinstance(name, str) or not name.strip():
            raise SystemExit(f"{path}: parts[{index}].name is required")
        if not isinstance(url, str) or not isinstance(note, str):
            raise SystemExit(f"{path}: parts[{index}] url and note must be strings")
        url = url.strip()
        if url and not url.startswith(("https://", "http://")):
            raise SystemExit(f"{path}: parts[{index}].url must be an http(s) link or empty")
        cleaned.append({"name": name.strip(), "url": url, "note": note.strip()})
    meta["parts"] = cleaned
    meta["video_id"] = youtube_id(meta["video"])
    return meta


def render_parts_box(parts: list[dict]) -> str:
    linked = [part for part in parts if part.get("url")]
    if not linked:
        return ""
    items = []
    for part in linked:
        note = f'<span class="part-note">{esc(part["note"])}</span>' if part.get("note") else ""
        items.append(
            f'<li><a href="{esc(part["url"])}">{esc(part["name"])}</a>{note}</li>'
        )
    return (
        '<aside class="parts-box" id="get-the-parts">'
        "<h2>Get the parts</h2>"
        f'<ul>{"".join(items)}</ul>'
        '<p class="affiliate">If a link is an affiliate link, Timber &amp; Tinker may earn a commission when you buy, at no extra cost to you.</p>'
        "</aside>\n"
    )


def render_video(video: str, title: str) -> str:
    video_id = youtube_id(video)
    if not video_id:
        return ""
    src = f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0"
    return (
        '<section class="watch" id="watch-the-build">'
        "<h2>Watch the build</h2>"
        '<div class="video-frame">'
        f'<iframe src="{src}" title="Watch the build: {esc(title)}" '
        'loading="lazy" allowfullscreen '
        'referrerpolicy="strict-origin-when-cross-origin"></iframe>'
        "</div>"
        f'<p class="print-only">Watch the build: https://www.youtube.com/watch?v={video_id}</p>'
        "</section>\n"
    )


def insert_before_heading(page: str, heading_id: str, snippet: str) -> tuple[str, bool]:
    match = re.search(rf'<h2 id="{re.escape(heading_id)}"', page)
    if not match or not snippet:
        return page, False
    return page[: match.start()] + snippet + page[match.start() :], True


def insert_after_section(page: str, heading_id: str, snippet: str) -> tuple[str, bool]:
    match = re.search(rf'<h2 id="{re.escape(heading_id)}"[^>]*>.*?</h2>', page, re.S)
    if not match or not snippet:
        return page, False
    rest = page[match.end() :]
    nxt = re.search(r"<h2\b", rest)
    if not nxt:
        return page + snippet, True
    pos = match.end() + nxt.start()
    return page[:pos] + snippet + page[pos:], True


def insert_banner(page: str, banner: str) -> str:
    # A subtitle (h2) and the blockquote under it stay directly beneath the title.
    match = re.match(
        r"\s*<h1\b[^>]*>.*?</h1>\s*"
        r"(?:<h2\b[^>]*>.*?</h2>\s*)?"
        r"(?:<blockquote\b[^>]*>.*?</blockquote>\s*)?"
        r"(?:<p>\s*<em>.*?</em>\s*</p>\s*)?",
        page,
        re.S,
    )
    if not match:
        return banner + page
    return page[: match.end()] + banner + page[match.end() :]


def project_banner(prefix: str) -> str:
    return (
        '<div class="project-banner">'
        '<p class="safety-pointer">Before you pick up a tool, read '
        f'<a href="{prefix}before-you-build/">Before you build</a>.</p>'
        '<p class="enlarge-hint">Select a drawing to see it larger.</p>'
        '<p class="print-row"><button type="button" class="js-print">Print this plan</button></p>'
        "</div>\n"
    )


def first_image(text: str) -> tuple[str, str]:
    match = re.search(r"!\[([^\]]*)\]\(([^)\s]+\.png)\)", text)
    if match:
        return match.group(2), match.group(1).strip()
    match = re.search(r"`([\w.-]+\.png)`", text)
    if match:
        return match.group(1), ""
    return "", ""


def field(text: str, label: str) -> str:
    bold = re.search(rf"^\*\*{re.escape(label)}:\*\*\s*(.+)$", text, re.M)
    if bold:
        return bold.group(1).strip()
    table = re.search(rf"^\|\s*\*\*{re.escape(label)}\*\*\s*\|\s*(.+?)\s*\|\s*$", text, re.M)
    if table:
        return table.group(1).strip()
    return ""


def title_and_tagline(text: str) -> tuple[str, str]:
    lines = text.splitlines()
    title = ""
    tagline = ""
    for index, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            for nxt in lines[index + 1 : index + 15]:
                stripped = nxt.strip()
                if not stripped or stripped.startswith("#") or stripped.startswith(">"):
                    continue
                if stripped.startswith("*") and stripped.endswith("*") and not stripped.startswith("**"):
                    tagline = stripped.strip("*").strip()
                break
            break
    return title, tagline


def referenced_pngs(text: str) -> list[str]:
    found = re.findall(r"[\w.-]+\.png", text)
    seen: list[str] = []
    for name in found:
        if PNG_NAME.fullmatch(name) and name not in seen:
            seen.append(name)
    return seen


def layout(
    *,
    title: str,
    description: str,
    canonical: str,
    body: str,
    depth: int,
    current: str,
    repository: str,
    lightbox: bool,
    section_nav: list[dict] | None = None,
) -> str:
    prefix = "../" * depth
    home_href = prefix or "./"

    def nav_link(key: str, href: str, label: str) -> str:
        current_attr = ' aria-current="page"' if key == current else ""
        return f'<li><a href="{href}"{current_attr}>{label}</a></li>'

    nav_items = [nav_link("home", home_href, "Projects")]
    for spec in section_nav or []:
        anchor = f"{prefix}#{spec['id']}" if prefix else f"#{spec['id']}"
        nav_items.append(nav_link(spec["id"], anchor, esc(spec["heading"])))
    nav_items.append(nav_link("before", f"{prefix}before-you-build/", "Before you build"))
    nav_items.append(nav_link("about", f"{prefix}about/", "About"))
    nav = "".join(nav_items)
    dialog = LIGHTBOX if lightbox else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{esc(description)}">
  <meta name="color-scheme" content="light">
  <title>{esc(title)}</title>
  <link rel="canonical" href="{esc(canonical)}">
  <link rel="icon" href="{prefix}favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="{prefix}assets/site.css">
</head>
<body>
  <a class="skip-link" href="#content">Skip to content</a>
  <header class="site-header">
    <p class="wordmark"><a href="{home_href}">Timber &amp; Tinker</a></p>
    <nav class="site-nav" aria-label="Site">
      <ul>
        {nav}
      </ul>
    </nav>
  </header>
  <main id="content" class="sheet">
{body}
  </main>
  <footer class="site-footer">
    <p><a href="{prefix}before-you-build/">Before you build</a></p>
    <p>Instructions and drawings are <a href="https://creativecommons.org/licenses/by-nc/4.0/">CC BY-NC 4.0</a> (<a href="{esc(repository)}/blob/main/LICENSE-CONTENT.md">license file</a>). Site code is <a href="{esc(repository)}/blob/main/LICENSE">MIT</a>.</p>
    <p><a href="{esc(repository)}">Timber &amp; Tinker on GitHub</a></p>
  </footer>
  {dialog}
  <script src="{prefix}assets/site.js"></script>
</body>
</html>
"""


def canonical_url(site: dict, path: str) -> str:
    custom = (site.get("customDomain") or "").strip()
    if custom:
        base = "https://" + custom
    else:
        base = site["pagesHost"].rstrip("/")
    if not path:
        return base + "/"
    return base + "/" + path.lstrip("/")


def write_page(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def load_projects() -> list[dict]:
    projects = []
    if not PROJECTS.is_dir():
        return projects
    for folder in sorted(PROJECTS.iterdir()):
        if not folder.is_dir():
            continue
        source = folder / "PROJECT.md"
        if not source.exists():
            continue
        text = source.read_text(encoding="utf-8")
        title, tagline = title_and_tagline(text)
        if not title:
            raise SystemExit(f"{source} needs a level-1 heading")
        meta = load_project_meta(folder)
        image, image_alt = first_image(text)
        pngs = {}
        for png in folder.glob("*.png"):
            pngs[png.name] = png_size(png)
        missing = [name for name in referenced_pngs(text) if name not in pngs]
        if missing:
            raise SystemExit(f"{source} names missing drawings: {', '.join(missing)}")
        unreferenced = sorted(set(pngs) - set(referenced_pngs(text)))
        if unreferenced:
            print(f"warning: {folder.name} has drawings not named in PROJECT.md: {', '.join(unreferenced)}")
        projects.append(
            {
                "slug": folder.name,
                "folder": folder,
                "text": text,
                "title": title,
                "tagline": tagline,
                "ages": field(text, "Ages"),
                "time": field(text, "Time to build"),
                "difficulty": field(text, "Difficulty"),
                "image": image,
                "image_alt": image_alt or title,
                "order": meta["order"],
                "section": meta["section"],
                "video": meta["video"],
                "parts": meta["parts"],
                "sizes": pngs,
            }
        )
    section_index = {key: index for index, key in enumerate(SECTIONS)}
    projects.sort(key=lambda item: (section_index[item["section"]], item["order"], item["title"].lower()))
    return projects


def render_project_body(project: dict, prefix: str) -> str:
    body = render_markdown(project["text"], project["sizes"])
    body = insert_banner(body, project_banner(prefix))
    parts_html = render_parts_box(project["parts"])
    if parts_html:
        body, placed = insert_after_section(body, "parts", parts_html)
        if not placed:
            body, placed = insert_before_heading(body, "cut-list", parts_html)
        if not placed:
            body, placed = insert_before_heading(body, "assembly", parts_html)
        if not placed:
            print(f"warning: {project['slug']} has part links but no Parts section to attach them to")
            body += parts_html
    video_html = render_video(project["video"], project["title"])
    if video_html:
        body, placed = insert_before_heading(body, "assembly", video_html)
        if not placed:
            body += video_html
    return body


def sections_for_nav(projects: list[dict]) -> list[dict]:
    present = {project["section"] for project in projects}
    return [spec for key, spec in SECTIONS.items() if spec.get("nav") and key in present]


def project_card(project: dict) -> str:
    image = ""
    if project["image"]:
        width, height = project["sizes"].get(project["image"], (0, 0))
        dims = f' width="{width}" height="{height}"' if width else ""
        image = (
            f'<img src="projects/{esc(project["slug"])}/{esc(project["image"])}" '
            f'alt="{esc(project["image_alt"])}"{dims}>'
        )
    tagline = f'<p class="tagline">{esc(project["tagline"])}</p>' if project["tagline"] else ""
    badge = ""
    if re.search(r"^## Conceptual Only\b", project["text"], re.M):
        badge = '<p class="badge">Conceptual Only</p>'
    return (
        '<li class="project-card">'
        f'<h3><a href="projects/{esc(project["slug"])}/">{esc(project["title"])}</a></h3>'
        f"{badge}"
        f"{image}"
        f"{tagline}"
        '<dl class="meta">'
        f"<div><dt>Ages</dt><dd>{esc(project['ages'])}</dd></div>"
        f"<div><dt>Time</dt><dd>{esc(project['time'])}</dd></div>"
        f"<div><dt>Difficulty</dt><dd>{esc(project['difficulty'])}</dd></div>"
        "</dl></li>"
    )


def bridge_choice(projects: list[dict]) -> str:
    slugs = {project["slug"] for project in projects}
    if "leonardo-bridge" not in slugs or "leonardo-bridge-2x4" not in slugs:
        return ""
    return (
        '<p class="bridge-choice">Leonardo’s bridge comes two ways: '
        'a <a href="projects/leonardo-bridge/">dowel model for the table</a>, '
        'and a <a href="projects/leonardo-bridge-2x4/">2x4 arch for the yard</a>.</p>'
    )


def home_body(projects: list[dict]) -> str:
    grouped: dict[str, list[dict]] = {key: [] for key in SECTIONS}
    for project in projects:
        grouped[project["section"]].append(project)
    blocks = [
        "<h1>Timber &amp; Tinker</h1>",
        '<p class="lede">Wood projects for kids and families, inspired by Leonardo da Vinci, with a drawing for every step.</p>',
        '<p class="mission">The aim is to get kids outdoors, teach real building skills, and spend time building together.</p>',
    ]
    for key, spec in SECTIONS.items():
        items = grouped[key]
        if not items:
            continue
        blocks.append(f'<h2 id="{esc(spec["id"])}">{esc(spec["heading"])}</h2>')
        if key == "kids":
            blocks.append(bridge_choice(items))
        elif spec["intro"]:
            blocks.append(f'<p class="section-intro">{esc(spec["intro"])}</p>')
        blocks.append(f'<ul class="project-list">{"".join(project_card(item) for item in items)}</ul>')
    return '<article class="home">\n' + "\n".join(blocks) + "\n</article>"


def check_site(projects: list[dict]) -> None:
    errors: list[str] = []
    site_root = OUT.resolve()
    html_files = list(OUT.rglob("*.html"))
    if not html_files:
        raise SystemExit("Build produced no HTML")
    linked_slugs = {project["slug"] for project in projects if any(part["url"] for part in project["parts"])}
    video_slugs = {project["slug"] for project in projects if project["video"].strip()}
    for page in html_files:
        text = page.read_text(encoding="utf-8")
        relative = page.relative_to(OUT).as_posix()
        for bad in (
            "google-analytics",
            "googletagmanager",
            "fonts.googleapis",
            "fonts.gstatic",
            "doubleclick",
            "facebook.net",
            "hotjar",
            "cookieconsent",
            "segment.com",
        ):
            if bad in text:
                errors.append(f"{relative}: unexpected third-party reference {bad}")
        if "<iframe" in text and "youtube-nocookie.com/embed/" not in text:
            errors.append(f"{relative}: iframe is not a YouTube privacy-enhanced embed")
        slug = page.parent.name if page.parent.parent == OUT / "projects" else ""
        if "Get the parts" in text and slug not in linked_slugs:
            errors.append(f"{relative}: parts box is visible without any part links")
        if "affiliate" in text.lower() and slug not in linked_slugs:
            errors.append(f"{relative}: affiliate disclosure is visible without any part links")
        if "watch-the-build" in text and slug not in video_slugs:
            errors.append(f"{relative}: video slot is visible without a video")
        for match in re.finditer(r"""(?:href|src)\s*=\s*["']([^"']+)["']""", text):
            url = match.group(1)
            if url.startswith(("https://", "http://", "data:", "mailto:", "#")):
                continue
            if url.startswith("/"):
                errors.append(f"{relative}: root-absolute URL {url}")
                continue
            bare = url.split("#", 1)[0].split("?", 1)[0]
            if not bare:
                continue
            target = (page.parent / bare).resolve()
            try:
                target.relative_to(site_root)
            except ValueError:
                errors.append(f"{relative}: link escapes the site: {url}")
                continue
            if bare.endswith("/"):
                target = target / "index.html"
            if not target.is_file():
                errors.append(f"{relative}: broken link {url}")
    for project in projects:
        page = (OUT / "projects" / project["slug"] / "index.html").read_text(encoding="utf-8")
        for name in project["sizes"]:
            if f'src="{name}"' not in page:
                errors.append(f"{project['slug']}: drawing {name} is not on the page")
        if "Before you build" not in page:
            errors.append(f"{project['slug']}: missing the Before you build pointer")
        for label, value in (("Ages", project["ages"]), ("Time", project["time"]), ("Difficulty", project["difficulty"])):
            if not value:
                errors.append(f"{project['slug']}: could not read {label} for the home card")
    if errors:
        raise SystemExit("Site check failed:\n- " + "\n- ".join(errors))


def self_check() -> None:
    sample = (
        "# Title\n\n*Tag line.*\n\n"
        "**Ages:** 8 and up\n**Time to build:** 1 hour\n**Difficulty:** 2 out of 5\n\n"
        "## Parts\n\n**Lumber**\n- Dowel, 16 inches\n\n"
        "![Parts](01-a.png)\n`01-a.png`\n\n"
        "## Cut list\n\nSee `01-a.png` in the list above.\n\n"
        "## Assembly\n\n### 1. Do the thing\n\nDo it carefully.\n\n"
        "`02-b.png` · `03-c.png`\n\n"
        "**Look for:** A snug fit.\n"
    )
    sizes = {"01-a.png": (10, 8), "02-b.png": (10, 8), "03-c.png": (12, 8)}
    rendered = render_markdown(sample, sizes)
    assert rendered.count("<img ") == 3, rendered
    assert rendered.count('src="01-a.png"') == 1
    assert "See <code>01-a.png</code>" in rendered
    assert "<li>Dowel, 16 inches</li>" in rendered
    assert 'class="look-for"' in rendered
    assert 'class="facts"' in rendered and "<br>" in rendered
    assert 'id="parts"' in rendered and 'id="assembly"' in rendered
    assert 'alt="Do the thing"' in rendered
    assert 'alt="Do the thing, drawing 2"' in rendered
    assert render_parts_box([{"name": "Dowel", "url": "", "note": "x"}]) == ""
    linked = render_parts_box([{"name": "Dowel", "url": "https://example.com/d", "note": "16 in"}])
    assert "Get the parts" in linked and "affiliate" in linked.lower() and "https://example.com/d" in linked
    assert render_video("", "Bridge") == ""
    video = render_video("https://www.youtube.com/watch?v=abcdefghijk", "Bridge")
    assert "abcdefghijk" in video and "youtube-nocookie.com" in video
    assert youtube_id("https://youtu.be/abcdefghijk") == "abcdefghijk"


def main() -> None:
    self_check()
    site = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
    custom = (site.get("customDomain") or "").strip()
    if custom and not re.fullmatch(r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}", custom):
        raise SystemExit("site.json customDomain must be a bare hostname, such as timberandtinker.org")
    for key in ("name", "repository", "pagesHost"):
        if not site.get(key):
            raise SystemExit(f"site.json is missing {key}")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    (OUT / "assets").mkdir()
    shutil.copy2(SRC / "site.css", OUT / "assets" / "site.css")
    shutil.copy2(SRC / "site.js", OUT / "assets" / "site.js")
    shutil.copy2(SRC / "favicon.svg", OUT / "favicon.svg")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    if custom:
        (OUT / "CNAME").write_text(custom + "\n", encoding="utf-8")

    projects = load_projects()
    if not projects:
        raise SystemExit("No projects found. Add a folder under projects/ with a PROJECT.md.")

    repository = site["repository"].rstrip("/")
    section_nav = sections_for_nav(projects)
    home = layout(
        title="Timber & Tinker",
        description="Wood projects for kids and families, inspired by Leonardo da Vinci, with a drawing for every step.",
        canonical=canonical_url(site, ""),
        body=home_body(projects),
        depth=0,
        current="home",
        repository=repository,
        lightbox=False,
        section_nav=section_nav,
    )
    write_page(OUT / "index.html", home)

    disclaimer_text = (CONTENT / "DISCLAIMER.md").read_text(encoding="utf-8")
    disclaimer_html = render_markdown(disclaimer_text, {})
    write_page(
        OUT / "before-you-build" / "index.html",
        layout(
            title="Before you build — Timber & Tinker",
            description="Read this before you start a Timber & Tinker project.",
            canonical=canonical_url(site, "before-you-build/"),
            body=f'<article class="page-prose">\n{disclaimer_html}\n</article>',
            depth=1,
            current="before",
            repository=repository,
            lightbox=False,
            section_nav=section_nav,
        ),
    )

    about_html = render_markdown((CONTENT / "about.md").read_text(encoding="utf-8"), {})
    write_page(
        OUT / "about" / "index.html",
        layout(
            title="About — Timber & Tinker",
            description="Timber & Tinker is a free, open-source collection of wood projects for kids and families.",
            canonical=canonical_url(site, "about/"),
            body=f'<article class="page-prose">\n{about_html}\n</article>',
            depth=1,
            current="about",
            repository=repository,
            lightbox=False,
            section_nav=section_nav,
        ),
    )

    for project in projects:
        destination = OUT / "projects" / project["slug"]
        destination.mkdir(parents=True, exist_ok=True)
        for name in project["sizes"]:
            shutil.copy2(project["folder"] / name, destination / name)
        description = project["tagline"] or project["title"]
        page = layout(
            title=f"{project['title']} — Timber & Tinker",
            description=description,
            canonical=canonical_url(site, f"projects/{project['slug']}/"),
            body=f'<article class="project">\n{render_project_body(project, "../../")}\n</article>',
            depth=2,
            current="project",
            repository=repository,
            lightbox=True,
            section_nav=section_nav,
        )
        write_page(OUT / "projects" / project["slug"] / "index.html", page)

    check_site(projects)
    print(f"Built {len(projects)} projects into {OUT}")
    for project in projects:
        links = sum(1 for part in project["parts"] if part["url"])
        video = "video" if project["video"].strip() else "no video"
        print(f"  {project['slug']}: {len(project['sizes'])} drawings, {links} part links, {video}")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        raise SystemExit(f"Self-check failed: {exc}") from exc
