import pytest

from corpus import queue as q

SOURCES = """
### 2.1 Product / e-commerce (47)
| # | URL | Platform | Vert | Description |
|---|---|---|---|---|
| P1 | https://vimeo.com/1114583666 | Vimeo | ? | Kasra Design: beauty product |
| P12 | https://vimeo.com/165443420 | Vimeo | n | ManvsMachine: Nike Flyknit |
| P18 | https://www.behance.net/gallery/1/x | Behance | ? | perfume |
| P38 | https://www.youtube.com/shorts/gEJncZLWsJE | YT Shorts | y | Pepsi MAX can |
"""


def test_parse_sources_rows():
    items = q.parse_sources(SOURCES)
    assert [i["id"] for i in items] == ["src-p1", "src-p12", "src-p18", "src-p38"]
    p38 = items[-1]
    assert p38 == {"id": "src-p38", "kind": "link", "url": "https://www.youtube.com/shorts/gEJncZLWsJE",
                   "platform": "youtube", "category": "product", "vertical": "y",
                   "description": "Pepsi MAX can", "status": "candidate"}


def test_pick_order_link_only_youtube_vimeo_vertical_then_top_tier():
    items = q.parse_sources(SOURCES)
    order = [i["id"] for i in q.pick_order(items, "product")]
    assert order == ["src-p38", "src-p1", "src-p12"]  # behance excluded; y > ? > n; top tier breaks ties only


def test_nominate_stock_one_url_domain_checked():
    items = []
    lic = {"name": "Pexels License", "url": "https://www.pexels.com/license/", "checkedAt": "2026-09-26",
           "restricted": False}
    it = q.nominate_stock(items, platform="pexels", url="https://www.pexels.com/video/abc-123/",
                          category="product", why="macro liquid", licence=lic, picked_by="claude-in-chrome")
    assert it["status"] == "picked" and it["kind"] == "stock" and items == [it]
    with pytest.raises(ValueError, match="domain"):
        q.nominate_stock(items, platform="pexels", url="https://mixkit.co/x", category="product",
                         why="x", licence=lic, picked_by="x")
    with pytest.raises(ValueError, match="duplicate"):
        q.nominate_stock(items, platform="pexels", url="https://www.pexels.com/video/abc-123/",
                         category="product", why="x", licence=lic, picked_by="x")


def test_status_and_progress():
    items = q.parse_sources(SOURCES)
    q.set_status(items, "src-p38", "studied")
    q.set_status(items, "src-p1", "rejected", "ai_generated")
    with pytest.raises(ValueError):
        q.set_status(items, "src-p12", "rejected", "meh")
    prog = q.progress(items)
    assert prog["link"]["product"] == {"studied": 1, "target": q.FIRST_CUT["link"]["product"]}


def test_save_load_roundtrip_is_sorted(tmp_path):
    items = list(reversed(q.parse_sources(SOURCES)))
    f = tmp_path / "queue.jsonl"
    q.save(items, f)
    assert [i["id"] for i in q.load(f)] == sorted(i["id"] for i in items)
