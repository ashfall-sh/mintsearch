"""
Read a Mintlify project's pages into a search index.

The index is built from the source `.mdx` files, not the exported html: the
source has the headings and words without the theme around them, so each page
becomes its title, description, navigation group and one entry per heading.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HEADING = re.compile(r"^(#{1,4})\s+(.*)$")
FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
FIELD = re.compile(r'^(title|description)\s*:\s*["\']?(.*?)["\']?\s*$', re.MULTILINE)
IMPORT = re.compile(r"^(?:import|export)\s+.*$", re.MULTILINE)
TAG = re.compile(r"</?[A-Z][A-Za-z0-9.]*[^>]*>")
ATTR = re.compile(r'(?:title|label|path|type|icon|href)="([^"]{2,90})"')
LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
COMMENT = re.compile(r"\{/\*.*?\*/\}", re.DOTALL)
SPACE = re.compile(r"[ \t]+")
# one section's text at most, so a long reference page can't swell the index
LONGEST = 4000


def pages(config: dict) -> list[tuple[str, str]]:
    """
    Every page in docs.json, with the group it sits under.

    Mintlify nests navigation several ways (groups, tabs, anchors, dropdowns,
    versions, languages), and a group can hold another group. Walking every
    `pages` list wherever it appears covers all of them.
    """
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    def walk(node, group: str, listed: bool) -> None:
        # a bare string is a page only inside a `pages` list; anywhere else it
        # is a label, an icon or a url
        if isinstance(node, str):
            if listed and node not in seen:
                seen.add(node)
                found.append((node, group))
            return
        if isinstance(node, list):
            for item in node:
                walk(item, group, listed)
            return
        if isinstance(node, dict):
            label = str(node.get("group") or group)
            for key, value in node.items():
                if key == "global":
                    continue
                if isinstance(value, (dict, list)):
                    walk(value, label, key == "pages")

    walk(config.get("navigation") or {}, "", False)
    return found


def readable(body: str) -> str:
    """The words on a page: components out, the text inside them and their labels kept."""
    body = IMPORT.sub("", body)
    body = COMMENT.sub("", body)
    body = FENCE.sub(lambda match: match.group(1), body)
    kept = []
    for tag in TAG.finditer(body):
        kept.extend(ATTR.findall(tag.group(0)))
    body = TAG.sub(" ", body)
    body = LINK.sub(lambda match: match.group(1), body)
    # a table row reads as its cells, not as one run-on line
    body = body.replace("|", " ").replace("`", "").replace("*", "")
    if kept:
        body += "\n" + " ".join(kept)
    return body


def sections(body: str) -> list[dict]:
    """A page as its headings and the text under each."""
    found = [{"heading": "", "text": []}]
    for line in body.split("\n"):
        match = HEADING.match(line.strip())
        if match:
            found.append({"heading": match.group(2).strip(), "text": []})
            continue
        line = SPACE.sub(" ", line).strip()
        if line and not line.startswith("---"):
            found[-1]["text"].append(line)
    return [
        {"heading": item["heading"], "text": " ".join(item["text"])[:LONGEST]}
        for item in found
        if item["text"] or item["heading"]
    ]


def source(root: Path, url: str) -> Path | None:
    """The file a page comes from: `.mdx` first, then `.md`."""
    for suffix in (".mdx", ".md"):
        path = root / f"{url}{suffix}"
        if path.exists():
            return path
    return None


def page(root: Path, url: str, group: str) -> dict | None:
    path = source(root, url)
    if path is None:
        return None
    raw = path.read_text(encoding="utf8")
    front = FRONT.match(raw)
    values = dict(FIELD.findall(front.group(1))) if front else {}
    body = raw[front.end():] if front else raw
    return {
        "url": "/" + url.strip("/"),
        "title": values.get("title") or url.rsplit("/", 1)[-1].replace("-", " "),
        "description": values.get("description", ""),
        "group": group,
        "sections": sections(readable(body)),
    }


def build(root: Path) -> list[dict]:
    """Every page the project's docs.json lists, read into index entries."""
    config = json.loads((root / "docs.json").read_text(encoding="utf8"))
    found = []
    for url, group in pages(config):
        entry = page(root, url, group)
        if entry is not None:
            found.append(entry)
    return found
