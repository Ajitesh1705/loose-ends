"""Extraction call: source artifact -> ExtractionResult (strict structured output).

The system prompt is the versioned file; the user message frames the artifact so the
model knows whose perspective "Me"/"i_owe" is and what channel it came from.
"""

from datetime import datetime
from pathlib import Path

from app.config import get_settings
from app.llm.client import get_llm_client
from app.models import Source
from app.schemas.extraction import ExtractionResult

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "extract_v1.md"
SYSTEM_PROMPT = _PROMPT_PATH.read_text()

_KIND_LABEL = {
    "call_transcript": "call transcript",
    "email_thread": "email thread",
    "whatsapp_export": "WhatsApp export",
    "session_note": "session note",
}


def _build_user(source: Source) -> str:
    ts = source.channel_ts.isoformat() if source.channel_ts else "unknown"
    hint = source.contact_hint or "unknown"
    label = _KIND_LABEL.get(source.kind, source.kind)
    return (
        f"Artifact type: {label}\n"
        f"Date of the communication: {ts}\n"
        f"Likely counterparty (hint, may be wrong): {hint}\n"
        f'"Me" / the account owner is the person whose commitments we track.\n\n'
        f"--- SOURCE START ---\n{source.raw_text}\n--- SOURCE END ---"
    )


def extract_commitments(source: Source) -> ExtractionResult:
    settings = get_settings()
    client = get_llm_client()
    return client.structured(
        kind="extract",
        model=settings.openai_model_extract,
        system=SYSTEM_PROMPT,
        user=_build_user(source),
        schema=ExtractionResult,
        temperature=0.0,
    )
