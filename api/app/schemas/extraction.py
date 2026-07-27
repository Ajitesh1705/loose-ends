"""The structured-output contract for extraction.

`ExtractionResult` is what the LLM must return (strict JSON schema, enforced in
llm/client.py). Fields mirror plan.md §Phase 2 exactly. The model returns a verbatim
`quote`, never character offsets, and never a resolved date — only `due_raw`.
"""

from typing import Literal

from pydantic import BaseModel, Field


class ExtractedCommitment(BaseModel):
    direction: Literal["i_owe", "they_owe"]
    what: str = Field(description="One imperative sentence: the promised action.")
    who: str = Field(description="The other party's name as it appears in the source.")
    due_raw: str | None = Field(
        description="The deadline phrase verbatim, e.g. 'by Friday'. Null if none."
    )
    confidence: float = Field(ge=0.0, le=1.0)
    quote: str = Field(
        description="Verbatim span from the source that supports this commitment."
    )
    ambiguity_note: str | None = Field(
        default=None,
        description=(
            "If anything is ambiguous (relative date, unclear party, conditional "
            "promise), a specific human-readable note. Null if unambiguous."
        ),
    )


class ExtractionResult(BaseModel):
    commitments: list[ExtractedCommitment]
