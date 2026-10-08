from memory.draft_groups import group_drafts


def _draft(name, parent=None, section="translation", exam_set=1):
    return {"draft_id": name, "revision_of": parent, "section": section,
            "filters": {"year": 2024, "month": 12, "exam_set": exam_set}, "ts": name}


def test_group_drafts_keeps_independent_and_orphaned_versions():
    drafts = [_draft("a"), _draft("b"), _draft("c", "a"), _draft("d", "missing"),
              _draft("e", "a", exam_set=2), _draft("f", "g"), _draft("g", "f")]
    groups = group_drafts(drafts)
    ids = [draft["draft_id"] for group in groups for draft in group["drafts"]]
    assert sorted(ids) == sorted(draft["draft_id"] for draft in drafts)
    assert len(ids) == len(set(ids))
    assert next(group for group in groups if group["root_id"] == "a")["drafts"][-1]["draft_id"] == "c"
    assert any(group["root_id"] == "d" for group in groups)
    assert any(group["root_id"] == "e" for group in groups)
