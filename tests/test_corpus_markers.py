"""Real-cache checks do not depend on the maintainer's private translation audit."""

from tests import conftest


def test_cached_paper_checks_run_without_private_audit(tmp_path, monkeypatch):
    cache = tmp_path / "parsed_papers"
    cache.mkdir()
    for number in range(38):
        (cache / f"paper_{number}.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(conftest, "__file__", str(tmp_path / "tests" / "conftest.py"))

    class Item:
        def __init__(self, keywords):
            self.keywords = keywords
            self.markers = []

        def add_marker(self, marker):
            self.markers.append(marker)

    corpus = Item({"local_corpus": True})
    audit = Item({"local_corpus": True, "local_audit": True})
    conftest.pytest_collection_modifyitems([corpus, audit])

    assert corpus.markers == []
    assert len(audit.markers) == 1
