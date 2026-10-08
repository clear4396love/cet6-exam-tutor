"""Group saved drafts by explicit, valid revision links only."""


def group_drafts(drafts: list[dict]) -> list[dict]:
    by_id = {draft["draft_id"]: draft for draft in drafts}

    def parent_of(draft):
        parent = by_id.get(draft.get("revision_of"))
        return parent if parent and parent["section"] == draft["section"] and parent["filters"] == draft["filters"] else None

    def root_of(draft):
        chain = []
        current = draft
        while current is not None and current["draft_id"] not in chain:
            chain.append(current["draft_id"])
            next_draft = parent_of(current)
            if next_draft is None:
                return current["draft_id"]
            current = next_draft
        return min(chain[chain.index(current["draft_id"]):])

    grouped = {}
    for draft in drafts:
        grouped.setdefault(root_of(draft), []).append(draft)
    result = []
    for root_id, members in grouped.items():
        members.sort(key=lambda item: item["ts"])
        root = by_id[root_id]
        result.append({"root_id": root_id, "section": root["section"],
                       "filters": root["filters"], "drafts": members,
                       "updated_at": members[-1]["ts"]})
    return sorted(result, key=lambda item: item["updated_at"], reverse=True)
