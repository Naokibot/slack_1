from pathlib import Path

from kosen_bot.db import Database
from kosen_bot.jma import JMA_EQ_FEED, JMA_EXTRA_FEED, JmaMonitor

FIXTURES = Path(__file__).parent / "fixtures"


def atom(entry_id: str, title: str, url: str) -> bytes:
    return f'''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><id>{entry_id}</id><title>{title}</title><updated>2026-08-14T04:25:00Z</updated><link href="{url}" type="application/xml"/></entry></feed>'''.encode()


class FakeClient:
    def __init__(self, mapping):
        self.mapping = mapping

    def get(self, url: str) -> bytes:
        return self.mapping[url]

    def close(self):
        pass


def test_earthquake_dedup_and_important_update(tmp_path: Path):
    eq_url = "https://example.test/eq.xml"
    mapping = {
        JMA_EQ_FEED: atom("eq-entry-1", "震源・震度に関する情報", eq_url),
        JMA_EXTRA_FEED: b'<feed xmlns="http://www.w3.org/2005/Atom"/>',
        eq_url: (FIXTURES / "earthquake_5lower.xml").read_bytes(),
    }
    posts = []
    db = Database(tmp_path / "bot.db")
    monitor = JmaMonitor(db, posts.append, lambda text: None, lambda text: None, client=FakeClient(mapping))
    monitor.poll()
    monitor.poll()
    assert len(posts) == 1

    mapping[JMA_EQ_FEED] = atom("eq-entry-2", "震源・震度に関する情報", eq_url)
    mapping[eq_url] = (FIXTURES / "earthquake_6lower.xml").read_bytes()
    monitor.poll()
    assert len(posts) == 2
    assert "更新" in posts[-1]
    assert "震度6弱" in posts[-1]


def test_warning_new_and_release_are_stateful(tmp_path: Path):
    warn_url = "https://example.test/warn.xml"
    mapping = {
        JMA_EQ_FEED: b'<feed xmlns="http://www.w3.org/2005/Atom"/>',
        JMA_EXTRA_FEED: atom("warn-entry-1", "気象警報・注意報", warn_url),
        warn_url: (FIXTURES / "shizuoka_warning.xml").read_bytes(),
    }
    posts = []
    db = Database(tmp_path / "bot.db")
    monitor = JmaMonitor(db, lambda text: None, posts.append, lambda text: None, client=FakeClient(mapping))
    monitor.poll()
    monitor.poll()
    assert len(posts) == 1
    assert "静岡市" in posts[0]
    assert "雷注意報" not in posts[0]

    mapping[JMA_EXTRA_FEED] = atom("warn-entry-2", "気象警報・注意報", warn_url)
    mapping[warn_url] = (FIXTURES / "shizuoka_release.xml").read_bytes()
    monitor.poll()
    assert len(posts) == 2
    assert "解除" in posts[-1]
