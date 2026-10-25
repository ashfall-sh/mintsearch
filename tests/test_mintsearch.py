import json
from pathlib import Path

from mintsearch import cli, index


def project(root: Path, navigation: dict) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "docs.json").write_text(json.dumps({"name": "acme docs", "description": "how acme works", "navigation": navigation}), encoding="utf8")
    return root


def mdx(root: Path, name: str, text: str) -> None:
    path = root / f"{name}.mdx"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf8")


def export(root: Path, *names: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for name in names:
        path = root / f"{name}.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<html><body><p>page</p></body></html>", encoding="utf8")
    return root


def test_pages_are_found_however_deeply_the_navigation_nests():
    navigation = {
        "tabs": [
            {"tab": "guides", "groups": [{"group": "start", "pages": ["index", {"group": "deeper", "pages": ["deep/one"]}]}]},
            {"tab": "api", "anchors": [{"anchor": "ref", "icon": "code", "pages": ["api/list"]}]},
        ],
        "global": {"anchors": [{"anchor": "site", "href": "https://example.com"}]},
    }
    assert index.pages({"navigation": navigation}) == [("index", "start"), ("deep/one", "deeper"), ("api/list", "")]


def test_a_page_reads_as_title_description_and_headed_sections(tmp_path):
    root = project(tmp_path / "src", {"groups": [{"group": "start", "pages": ["intro"]}]})
    mdx(root, "intro", '---\ntitle: "Intro"\ndescription: "the first page"\n---\nimport X from "x"\n\nhello <Note>keep this</Note>\n\n## setup\n\nrun `acme init` and [read more](/more)\n')
    [entry] = index.build(root)
    assert entry["url"] == "/intro" and entry["title"] == "Intro" and entry["description"] == "the first page" and entry["group"] == "start"
    assert entry["sections"][0]["text"] == "hello keep this"
    assert entry["sections"][1] == {"heading": "setup", "text": "run acme init and read more"}


def test_a_missing_page_is_skipped_not_fatal(tmp_path):
    root = project(tmp_path / "src", {"groups": [{"group": "g", "pages": ["here", "gone"]}]})
    mdx(root, "here", "# here\n\ntext")
    assert [entry["url"] for entry in index.build(root)] == ["/here"]


def test_run_writes_the_index_assets_and_tags_every_page_once(tmp_path):
    root = project(tmp_path / "src", {"groups": [{"group": "g", "pages": ["index", "guide/a"]}]})
    mdx(root, "index", "# home\n\nwelcome")
    mdx(root, "guide/a", "# a\n\nalpha")
    out = export(tmp_path / "out", "index", "guide/a")
    assert cli.run(out, root) == 0
    assert {"mintsearch.json", "mintsearch.js", "mintsearch.css"} <= {p.name for p in out.iterdir()}
    assert len(json.loads((out / "mintsearch.json").read_text())["pages"]) == 2
    page = (out / "guide" / "a.html").read_text()
    assert page.count("/mintsearch.js\"") == 1 and 'data-index="/mintsearch.json"' in page
    assert cli.run(out, root) == 0
    assert (out / "guide" / "a.html").read_text().count("/mintsearch.js\"") == 1
    assert not (out / "sitemap.xml").exists()


def test_site_writes_sitemap_robots_and_llms_under_a_base_path(tmp_path):
    root = project(tmp_path / "src", {"groups": [{"group": "start", "pages": ["index", "a"]}]})
    mdx(root, "index", '---\ntitle: "Home"\n---\nhi')
    mdx(root, "a", '---\ntitle: "A"\ndescription: "about a"\n---\nhi')
    out = export(tmp_path / "out", "index", "a")
    assert cli.run(out, root, site="https://docs.acme.dev/", base="docs/", head="<script>stats</script>") == 0
    assert "<loc>https://docs.acme.dev/docs/</loc><loc>" not in (out / "sitemap.xml").read_text()
    assert "<loc>https://docs.acme.dev/docs/</loc>" in (out / "sitemap.xml").read_text()
    assert "<loc>https://docs.acme.dev/docs/a</loc>" in (out / "sitemap.xml").read_text()
    assert "Sitemap: https://docs.acme.dev/docs/sitemap.xml" in (out / "robots.txt").read_text()
    llms = (out / "llms.txt").read_text()
    assert llms.startswith("# acme docs\n\n> how acme works") and "- [A](https://docs.acme.dev/docs/a): about a" in llms
    page = (out / "a.html").read_text()
    assert 'src="/docs/mintsearch.js"' in page and "<script>stats</script>" in page


def test_an_existing_robots_txt_is_kept(tmp_path):
    root = project(tmp_path / "src", {"pages": ["index"]})
    mdx(root, "index", "hi")
    out = export(tmp_path / "out", "index")
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /private\n")
    cli.run(out, root, site="https://x.dev")
    assert "Disallow: /private" in (out / "robots.txt").read_text()


def test_bad_paths_say_so(tmp_path, capsys):
    assert cli.run(tmp_path / "nope", tmp_path) == 2
    assert "no docs.json" in capsys.readouterr().err
