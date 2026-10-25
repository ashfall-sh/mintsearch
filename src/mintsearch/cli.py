"""
mintsearch: search, a sitemap and llms.txt for a self-hosted Mintlify export.

    mintsearch <export> --source <project> [--site https://docs.example.com]

<export>   the unpacked `mint export` folder, changed in place
<project>  the folder with docs.json and the .mdx pages (default: .)

Mintlify's search asks its cloud service, so an export that was never signed in
only shows "run mint login in the cli to activate search" in its search bar.
This writes an index beside the pages, puts a small search overlay on every
page that takes over the search bar and ctrl+k, and, given --site, writes the
sitemap.xml, robots.txt and llms.txt the export links to but never contains.
Running it twice over the same folder is safe.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from importlib import resources
from pathlib import Path

from mintsearch import __version__, index

MARK = "mintsearch.js"
ASSETS = ("mintsearch.js", "mintsearch.css")


def tags(base: str, head: str) -> str:
    """What goes on every page, just before </body>."""
    return (
        f'<link rel="stylesheet" href="{base}/mintsearch.css">'
        f'<script src="{base}/mintsearch.js" data-index="{base}/mintsearch.json" defer></script>'
        f"{head}"
    )


def inject(export: Path, snippet: str) -> tuple[int, int]:
    """Put the overlay on every html page. Returns (changed, already had it)."""
    changed = already = 0
    for html in export.rglob("*.html"):
        text = html.read_text(encoding="utf8", errors="ignore")
        if MARK in text:
            already += 1
            continue
        if "</body>" not in text:
            continue
        html.write_text(text.replace("</body>", f"{snippet}</body>", 1), encoding="utf8")
        changed += 1
    return changed, already


def address(site: str, base: str, url: str) -> str:
    return site.rstrip("/") + base + ("/" if url == "/index" else url)


def maps(export: Path, entries: list[dict], site: str, base: str, title: str, summary: str) -> None:
    """The files an unsigned export links to and leaves out."""
    urls = "".join(f"<url><loc>{address(site, base, item['url'])}</loc></url>" for item in entries)
    (export / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n',
        encoding="utf8",
    )
    robots = export / "robots.txt"
    if not robots.exists():
        robots.write_text(f"User-agent: *\nAllow: /\n\nSitemap: {site.rstrip('/')}{base}/sitemap.xml\n", encoding="utf8")
    lines = [f"# {title}", ""]
    if summary:
        lines += [f"> {summary}", ""]
    group = None
    for item in entries:
        if item["group"] != group:
            group = item["group"]
            if group:
                lines += ["", f"## {group}", ""]
        described = f": {item['description']}" if item["description"] else ""
        lines.append(f"- [{item['title']}]({address(site, base, item['url'])}){described}")
    (export / "llms.txt").write_text("\n".join(lines).strip() + "\n", encoding="utf8")


def run(export: Path, source: Path, site: str = "", base: str = "", title: str = "", summary: str = "", head: str = "") -> int:
    if not (source / "docs.json").exists():
        print(f"mintsearch: no docs.json in {source}", file=sys.stderr)
        return 2
    if not export.is_dir():
        print(f"mintsearch: {export} is not a folder", file=sys.stderr)
        return 2
    base = "/" + base.strip("/") if base.strip("/") else ""
    entries = index.build(source)
    (export / "mintsearch.json").write_text(json.dumps({"pages": entries}, separators=(",", ":")), encoding="utf8")
    for name in ASSETS:
        with resources.as_file(resources.files("mintsearch") / "assets" / name) as path:
            shutil.copyfile(path, export / name)
    changed, already = inject(export, tags(base, head))
    if site:
        config = json.loads((source / "docs.json").read_text(encoding="utf8"))
        maps(export, entries, site, base, title or str(config.get("name") or "docs"), summary or str(config.get("description") or ""))
    note = f", {already} already had it" if already else ""
    print(f"mintsearch: indexed {len(entries)} pages, search added to {changed} html files{note}" + (", sitemap.xml, robots.txt and llms.txt written" if site else ""))
    return 0 if entries and (changed or already) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mintsearch", description="search, a sitemap and llms.txt for a self-hosted Mintlify export")
    parser.add_argument("export", type=Path, help="the unpacked `mint export` folder, changed in place")
    parser.add_argument("--source", type=Path, default=Path("."), help="the folder with docs.json and the pages (default: .)")
    parser.add_argument("--site", default="", help="the public address, like https://docs.example.com; writes sitemap.xml, robots.txt and llms.txt")
    parser.add_argument("--base", default="", help="the path the docs are served under, like /docs (default: the root)")
    parser.add_argument("--title", default="", help="llms.txt heading (default: name in docs.json)")
    parser.add_argument("--summary", default="", help="llms.txt summary line (default: description in docs.json)")
    parser.add_argument("--head", type=Path, help="a file of html to add to every page too, like an analytics tag")
    parser.add_argument("--version", action="version", version=f"mintsearch {__version__}")
    args = parser.parse_args(argv)
    head = args.head.read_text(encoding="utf8") if args.head else ""
    return run(args.export, args.source, args.site, args.base, args.title, args.summary, head)


if __name__ == "__main__":
    raise SystemExit(main())
