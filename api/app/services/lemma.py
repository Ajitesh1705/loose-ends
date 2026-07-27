"""Lightweight lexical helpers for dedupe scoring — deterministic, no NLP downloads.

`lemma_overlap` is a Jaccard over crudely-lemmatized content tokens: it catches
"send the Q3 numbers" vs "sending Q3 audience numbers" without pretending to be spaCy.
It's a *secondary* signal (weight 0.25); embeddings carry the semantics.
"""

import re

_STOPWORDS = {
    "the", "a", "an", "to", "of", "for", "and", "or", "with", "in", "on", "at",
    "by", "i", "you", "he", "she", "they", "we", "it", "me", "him", "her", "them",
    "us", "my", "your", "his", "their", "our", "will", "'ll", "ill", "so", "that",
    "this", "over", "up", "get", "send",  # 'get'/'send' are near-universal here
}

# Explicit restatement / confirmation markers (plan.md §Phase 4). +0.15 when present.
_RESTATEMENT = [
    "as discussed", "as promised", "as agreed", "as we discussed",
    "confirming", "to confirm", "per our call", "per our conversation",
    "per our", "following up", "follow up on", "circling back", "to recap",
    "as mentioned", "like i said", "like we said", "reconfirming",
]


def _lemmatize(token: str) -> str:
    t = token.lower()
    for suffix in ("ing", "ed", "es", "s"):
        if len(t) - len(suffix) >= 3 and t.endswith(suffix):
            return t[: -len(suffix)]
    return t


def _content_lemmas(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {_lemmatize(t) for t in tokens if t not in _STOPWORDS and len(t) > 1}


def lemma_overlap(a: str, b: str) -> float:
    """Jaccard similarity of content lemmas in [0, 1]."""
    sa, sb = _content_lemmas(a), _content_lemmas(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def has_restatement_marker(text: str) -> bool:
    low = text.lower()
    return any(marker in low for marker in _RESTATEMENT)
