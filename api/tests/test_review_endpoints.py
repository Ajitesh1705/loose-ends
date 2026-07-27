from datetime import datetime, timezone

from app.models import Source
from app.schemas.extraction import ExtractedCommitment
from app.services.ingest import persist_extraction

RAW = "Me: I'll send the updated brand guidelines next week."


def _seed_review_item(db) -> str:
    """Create one needs_review commitment (vague deadline) and return its id."""
    source = Source(
        kind="call_transcript",
        title="t",
        raw_text=RAW,
        channel_ts=datetime(2026, 7, 21, 15, 0, tzinfo=timezone.utc),
    )
    db.add(source)
    db.flush()
    cand = ExtractedCommitment(
        direction="i_owe",
        what="Send updated brand guidelines",
        who="Priya",
        due_raw="next week",
        confidence=0.9,
        quote="I'll send the updated brand guidelines next week",
        ambiguity_note=None,
    )
    result = persist_extraction(db, source, [cand])
    db.commit()
    return str(result.created[0].id)


def test_review_lists_item_with_note_and_evidence(client, db):
    cid = _seed_review_item(db)
    resp = client.get("/review")
    assert resp.status_code == 200
    items = resp.json()
    item = next(i for i in items if i["id"] == cid)
    assert item["state"] == "needs_review"
    assert "next week" in item["ambiguity_note"]
    assert len(item["evidence"]) == 1


def test_confirm_applies_edits_and_activates(client, db):
    cid = _seed_review_item(db)
    resp = client.post(
        f"/commitments/{cid}/confirm",
        json={"what": "Send the final brand guidelines", "due_at": "2026-07-31T17:00:00Z"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "active"
    assert body["ambiguity_note"] is None
    assert body["what"] == "Send the final brand guidelines"
    assert body["due_precision"] == "exact"
    # no longer in the review queue
    assert all(i["id"] != cid for i in client.get("/review").json())


def test_reject_drops_and_leaves_queue(client, db):
    cid = _seed_review_item(db)
    resp = client.post(f"/commitments/{cid}/reject")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert all(i["id"] != cid for i in client.get("/review").json())
