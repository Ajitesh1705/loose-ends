"""Load 3 demo sources. Idempotent: does nothing if sources already exist.

These three double as the reproducible-demo fixtures behind the Ingest dropdown
(Phase 6) and overlap the eval segments (Phase 8): coach session note, agency client
call, freelancer WhatsApp thread.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Source

SEED_SOURCES = [
    {
        "kind": "session_note",
        "title": "Coaching session — Marcus D. (strength block)",
        "contact_hint": "Marcus Delgado",
        "channel_ts": datetime(2026, 7, 20, 9, 30, tzinfo=timezone.utc),
        "raw_text": (
            "Session with Marcus, week 3 of the strength block. Squat form looked much "
            "better today. He mentioned the knee twinge is gone.\n\n"
            "I told him I'd put together a revised 4-week program with the deadlift "
            "progression by this Friday so he can start Monday. Also promised to send "
            "over the mobility video I mentioned for his hips.\n\n"
            "Marcus is going to log his sleep for the next two weeks and send me the "
            "numbers before our next session. He said he'll try to hit 7 hours."
        ),
    },
    {
        "kind": "call_transcript",
        "title": "Client call — Northwind Co. Q3 campaign",
        "contact_hint": "Priya Raman",
        "channel_ts": datetime(2026, 7, 21, 15, 0, tzinfo=timezone.utc),
        "raw_text": (
            "Priya: Thanks for hopping on. Before we scale spend I want to see how Q3 is "
            "actually landing.\n"
            "Me: Totally. Yeah I'll get the Q3 audience breakdown over to you before "
            "Friday, with the age and geo splits.\n"
            "Priya: Perfect. And can you include the creative that's fatiguing?\n"
            "Me: Yep, I'll flag the fatiguing creatives in the same doc.\n"
            "Priya: Great. On our side, I'll get you the updated brand guidelines by "
            "early next week so the new creative is on-spec.\n"
            "Me: Appreciate it. Let's find time later this month to review the whole "
            "funnel.\n"
            "Priya: Sounds good."
        ),
    },
    {
        # Dedupe pair, part 1 (Tuesday call). The same promise is restated in the
        # confirming email below — Phase 4 should merge them into ONE commitment.
        "kind": "call_transcript",
        "title": "Client call — Meridian (pricing deck)",
        "contact_hint": "Priya Raman",
        "channel_ts": datetime(2026, 7, 21, 11, 0, tzinfo=timezone.utc),
        "raw_text": (
            "Priya: One more thing before we wrap — can you get me the updated pricing "
            "deck with the new tiers?\n"
            "Me: Yeah, for sure. I'll send Priya the updated pricing deck by Thursday.\n"
            "Priya: Perfect, that works."
        ),
    },
    {
        # Dedupe pair, part 2 (Wednesday confirming email). Restatement markers
        # ("as discussed", "confirming") + same promise + same contact + due within
        # the window -> auto-merge into the call commitment above.
        "kind": "email_thread",
        "title": "Email — Meridian pricing (confirming)",
        "contact_hint": "Priya Raman",
        "channel_ts": datetime(2026, 7, 22, 9, 15, tzinfo=timezone.utc),
        "raw_text": (
            "To: Priya Raman\n"
            "Subject: Re: pricing\n\n"
            "Hi Priya — as discussed on our call yesterday, just confirming that I'll "
            "send you the updated pricing deck by Thursday. Shout if anything else is "
            "needed in the meantime."
        ),
    },
    {
        "kind": "whatsapp_export",
        "title": "WhatsApp — Jordan (logo redesign)",
        "contact_hint": "Jordan Ellis",
        "channel_ts": datetime(2026, 7, 22, 18, 45, tzinfo=timezone.utc),
        "raw_text": (
            "[6:41 PM] Jordan: hey! any movement on the logo concepts?\n"
            "[6:43 PM] Me: yes! sending you three directions by tomorrow evening for "
            "sure\n"
            "[6:44 PM] Jordan: amazing. also did you get the invoice sorted?\n"
            "[6:46 PM] Me: I'll get the updated invoice to you by end of week\n"
            "[6:47 PM] Jordan: cool. my designer will send you the brand colors so you "
            "have them\n"
            "[6:48 PM] Me: perfect, no rush"
        ),
    },
]


def seed() -> None:
    with SessionLocal() as db:
        count = db.scalar(select(func.count()).select_from(Source))
        if count and count > 0:
            print(f"[seed] {count} sources already present, skipping.")
            return
        for row in SEED_SOURCES:
            db.add(Source(**row))
        db.commit()
        print(f"[seed] inserted {len(SEED_SOURCES)} sources.")


if __name__ == "__main__":
    seed()
