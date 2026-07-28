"""Author the labelled eval fixtures, then emit them as {id}.txt + {id}.labels.json.

Labels are HAND-AUTHORED ground truth (direction, who, normalized `what`, the human's
expected `due_at`, whether it genuinely needs review) — deliberately NOT computed by the
pipeline, so the eval measures the pipeline against a human, not against itself.

Anchor weekday reference (2026): 07-20 Mon · 07-21 Tue · 07-22 Wed · 07-23 Thu ·
07-24 Fri · 07-25 Sat · 07-26 Sun · 07-27 Mon · 07-28 Tue · 07-29 Wed · 07-31 Fri ·
08-03 Mon. Hard cases (politeness, retraction, third-party, conditional, ambiguous
anchor, cross-channel dedupe, zero-commitment) are included on purpose and labelled
honestly — fixtures are NOT tuned to make the numbers pretty.
"""

import json
from pathlib import Path

FIX = Path(__file__).resolve().parent / "fixtures"


def c(direction, who, what, due_at, needs_review=False):
    return {
        "direction": direction,
        "who": who,
        "what": what,
        "due_at": due_at,
        "needs_review": needs_review,
    }


# id, segment, kind, channel_ts, contact_hint, text, expected[], merge_group
FIXTURES = [
    # ───────────── COACH (session notes / whatsapp) ─────────────
    ("coach_01", "coach", "session_note", "2026-07-21T09:00:00Z", "Marcus Delgado",
     "Session with Marcus. Squat felt strong. I'll send the revised training program "
     "by Friday. He's going to log all his workouts this week and send them over.",
     [c("i_owe", "Marcus Delgado", "Send the revised training program", "2026-07-24"),
      c("they_owe", "Marcus Delgado", "Log workouts and send them", "2026-07-24", True)],
     None),

    ("coach_02", "coach", "session_note", "2026-07-22T10:00:00Z", "Dana Whitfield",
     "Dana asked whether I could pull together a meal template. I said I'll see what I "
     "can do. Nice session overall, her energy is better.",
     [], None),  # politeness, not a commitment

    ("coach_03", "coach", "session_note", "2026-07-23T09:30:00Z", "Marcus Delgado",
     "My nutritionist will send Marcus the macro sheet. On my side, I'll put together "
     "his deload week by Tuesday.",
     [c("i_owe", "Marcus Delgado", "Put together the deload week plan", "2026-07-28")],
     None),  # third-party 'nutritionist will send' must NOT be extracted

    ("coach_04", "coach", "session_note", "2026-07-24T16:00:00Z", "Dana Whitfield",
     "Told Dana I'd send the mobility routine tonight — actually scratch that, she's "
     "travelling next week, we'll pick it up when she's back.",
     [], None),  # retracted

    ("coach_05", "coach", "session_note", "2026-07-20T11:00:00Z", "Priyanka Rao",
     "If Priyanka signs off on the plan, I'll book the gym assessment for her. She said "
     "she'll confirm by Wednesday.",
     [c("they_owe", "Priyanka Rao", "Confirm sign-off on the plan", "2026-07-22"),
      c("i_owe", "Priyanka Rao", "Book the gym assessment", None, True)],
     None),  # conditional i_owe -> needs review

    ("coach_06", "coach", "session_note", "2026-07-27T09:00:00Z", "Marcus Delgado",
     "Sent Marcus his latest numbers. I'll prepare the next training block and share it "
     "by end of week.",
     [c("i_owe", "Marcus Delgado", "Prepare and share the next training block",
        "2026-07-31")],
     None),

    ("coach_07", "coach", "whatsapp_export", "2026-07-21T18:00:00Z", "Dana Whitfield",
     "[6:01 PM] Dana: how should I track meals?\n"
     "[6:02 PM] Me: just jot them in the app\n"
     "[6:03 PM] Dana: ok! I'll send you my food log in a couple of days",
     [c("they_owe", "Dana Whitfield", "Send her food log", "2026-07-23", True)],
     None),

    ("coach_08", "coach", "session_note", "2026-07-22T14:00:00Z", "Marcus Delgado",
     "Good chat with Marcus about competition prep. Let's touch base next week to map "
     "out the peak. Nothing else pressing.",
     [], None),  # 'let's touch base' politeness, zero commitments

    ("coach_09", "coach", "session_note", "2026-07-23T12:00:00Z", "Priyanka Rao",
     "I owe Priyanka the intake questionnaire by tomorrow, and I'll email her the class "
     "schedule as well.",
     [c("i_owe", "Priyanka Rao", "Send the intake questionnaire", "2026-07-24"),
      c("i_owe", "Priyanka Rao", "Email the class schedule", None)],
     None),

    # ───────────── AGENCY (calls / emails) ─────────────
    ("agency_01", "agency", "call_transcript", "2026-07-21T15:00:00Z", "Priya Raman",
     "Priya: where are we on the numbers?\n"
     "Me: I'll send the Q3 report by Thursday.\n"
     "Priya: great, thanks.",
     [c("i_owe", "Priya Raman", "Send the Q3 report", "2026-07-23")],
     "g_q3"),

    ("agency_02", "agency", "email_thread", "2026-07-22T09:00:00Z", "Priya Raman",
     "To: Priya Raman\nSubject: Re: Q3\n\nHi Priya — as discussed on our call, just "
     "confirming I'll send the Q3 report by Thursday.",
     [c("i_owe", "Priya Raman", "Send the Q3 report", "2026-07-23")],
     "g_q3"),  # same promise as agency_01 -> should merge into ONE

    ("agency_03", "agency", "call_transcript", "2026-07-20T14:00:00Z", "Tom Alvarez",
     "Tom: can you get us the SOW?\n"
     "Me: yes, I'll send the SOW by end of week.",
     [c("i_owe", "Tom Alvarez", "Send the SOW", "2026-07-24")],
     "g_tom"),

    ("agency_04", "agency", "email_thread", "2026-07-21T10:00:00Z", "Tom Alvarez",
     "To: Tom Alvarez\nSubject: billing\n\nHi Tom — I'll send the updated invoice by "
     "end of week.",
     [c("i_owe", "Tom Alvarez", "Send the updated invoice", "2026-07-24")],
     "g_tom"),  # distinct promise, same contact -> must NOT merge with the SOW

    ("agency_05", "agency", "call_transcript", "2026-07-22T13:00:00Z", "Sofia Marin",
     "Sofia: we should explore a retainer at some point.\n"
     "Me: yeah, let's find time to dig into it.",
     [], None),  # exploratory, no commitment

    ("agency_06", "agency", "email_thread", "2026-07-23T11:00:00Z", "Priya Raman",
     "To: Priya Raman\nSubject: creative\n\nI'll have the creative refresh over to you "
     "early next week.",
     [c("i_owe", "Priya Raman", "Send the creative refresh", "2026-08-03", True)],
     None),  # ambiguous relative anchor -> review

    ("agency_07", "agency", "call_transcript", "2026-07-27T16:00:00Z", "Tom Alvarez",
     "Me: I'll send revised pricing tomorrow.\n"
     "Tom: my team will review it and get back to you.",
     [c("i_owe", "Tom Alvarez", "Send revised pricing", "2026-07-28"),
      c("they_owe", "Tom Alvarez", "Review the pricing and respond", None)],
     None),

    ("agency_08", "agency", "email_thread", "2026-07-24T09:00:00Z", "Priya Raman",
     "To: Priya Raman\nSubject: correction\n\nIgnore my last note about sending the "
     "analytics deck today — we've paused that workstream for now.",
     [], None),  # retracted

    # ───────────── FREELANCER (whatsapp) ─────────────
    ("free_01", "freelancer", "whatsapp_export", "2026-07-21T18:30:00Z", "Jordan Ellis",
     "[6:30 PM] Jordan: any word on the logo?\n"
     "[6:31 PM] Me: sending 3 concepts by tomorrow evening\n"
     "[6:32 PM] Jordan: nice, my designer will send you the brand colors",
     [c("i_owe", "Jordan Ellis", "Send three logo concepts", "2026-07-22")],
     None),  # 'my designer will send' third-party must NOT be extracted

    ("free_02", "freelancer", "whatsapp_export", "2026-07-22T12:00:00Z", "Alex Kim",
     "[12:00 PM] Me: I'll get the updated invoice to you by end of week\n"
     "[12:01 PM] Alex: thanks! could you also tweak the header?\n"
     "[12:02 PM] Me: sure, I'll adjust the header",
     [c("i_owe", "Alex Kim", "Send the updated invoice", "2026-07-24"),
      c("i_owe", "Alex Kim", "Adjust the header", None)],
     None),

    ("free_03", "freelancer", "whatsapp_export", "2026-07-23T15:00:00Z", "Sam Doyle",
     "[3:00 PM] Me: if you approve the mockup, I'll ship the final assets by Monday\n"
     "[3:02 PM] Sam: will review this weekend",
     [c("i_owe", "Sam Doyle", "Ship the final assets", "2026-07-27", True),
      c("they_owe", "Sam Doyle", "Review the mockup", None, True)],
     None),  # conditional

    ("free_04", "freelancer", "whatsapp_export", "2026-07-24T17:00:00Z", "Jordan Ellis",
     "[5:00 PM] Me: I'll send the revised homepage mockup by Wednesday",
     [c("i_owe", "Jordan Ellis", "Send the revised homepage mockup", "2026-07-29")],
     "g_home"),

    ("free_05", "freelancer", "whatsapp_export", "2026-07-25T10:00:00Z", "Jordan Ellis",
     "[10:00 AM] Me: as promised, just confirming I'll send the revised homepage mockup "
     "by Wednesday",
     [c("i_owe", "Jordan Ellis", "Send the revised homepage mockup", "2026-07-29")],
     "g_home"),  # restatement -> should merge into free_04

    ("free_06", "freelancer", "whatsapp_export", "2026-07-26T09:00:00Z", "Alex Kim",
     "[9:00 AM] Alex: everything looks great, thanks so much!\n"
     "[9:01 AM] Me: 🙌 anytime",
     [], None),  # zero commitments

    ("free_07", "freelancer", "whatsapp_export", "2026-07-27T13:00:00Z", "Sam Doyle",
     "[1:00 PM] Sam: could you maybe look at the pricing page too?\n"
     "[1:01 PM] Me: I'll see what I can do",
     [], None),  # politeness, no commitment
]

# Expected merges per dedupe group (fixtures sharing a group are ingested together).
GROUP_EXPECTED_MERGES = {"g_q3": 1, "g_tom": 0, "g_home": 1}


def main() -> None:
    FIX.mkdir(parents=True, exist_ok=True)
    for fid, segment, kind, ts, hint, text, expected, group in FIXTURES:
        (FIX / f"{fid}.txt").write_text(text)
        labels = {
            "id": fid,
            "segment": segment,
            "kind": kind,
            "channel_ts": ts,
            "contact_hint": hint,
            "expected": expected,
            "merge_group": group,
        }
        (FIX / f"{fid}.labels.json").write_text(json.dumps(labels, indent=2))
    print(f"wrote {len(FIXTURES)} fixtures to {FIX}")
    print("groups:", GROUP_EXPECTED_MERGES)


if __name__ == "__main__":
    main()
