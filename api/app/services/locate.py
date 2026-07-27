"""Locate a model-returned verbatim quote inside the source text.

Models are bad at character counting, so extraction returns the quote *text*, not
offsets (plan.md §Phase 2). We find the offsets here, deterministically, in three
escalating passes:

  1. exact substring match
  2. normalized-whitespace + case-insensitive match (models re-flow whitespace and
     occasionally change case)
  3. fuzzy match with rapidfuzz, accepted only at score >= 90

If none locate the quote, the caller discards the commitment as a hallucination.
That discard is a feature and is counted in evals.
"""

from dataclasses import dataclass

from rapidfuzz import fuzz

FUZZY_THRESHOLD = 90.0


@dataclass(frozen=True)
class LocatedSpan:
    start: int
    end: int
    method: str  # 'exact' | 'normalized' | 'fuzzy'
    score: float


def _normalize_with_map(text: str) -> tuple[str, list[int]]:
    """Lowercase and collapse whitespace runs to single spaces.

    Returns the normalized string plus a map from each normalized-char index back
    to the original index in `text`, so a match found in normalized space can be
    projected back onto the original.
    """
    out_chars: list[str] = []
    index_map: list[int] = []
    prev_was_space = False
    for i, ch in enumerate(text):
        if ch.isspace():
            if prev_was_space:
                continue  # collapse the run
            out_chars.append(" ")
            index_map.append(i)  # the first whitespace char of the run
            prev_was_space = True
        else:
            out_chars.append(ch.lower())
            index_map.append(i)
            prev_was_space = False
    return "".join(out_chars), index_map


def locate_span(
    haystack: str, needle: str, fuzzy_threshold: float = FUZZY_THRESHOLD
) -> LocatedSpan | None:
    needle = needle.strip()
    if not needle:
        return None

    # 1. exact
    idx = haystack.find(needle)
    if idx != -1:
        return LocatedSpan(idx, idx + len(needle), "exact", 100.0)

    # 2. normalized whitespace + case
    norm_hay, index_map = _normalize_with_map(haystack)
    norm_needle, _ = _normalize_with_map(needle)
    norm_needle = norm_needle.strip()
    if norm_needle:
        nidx = norm_hay.find(norm_needle)
        if nidx != -1:
            start = index_map[nidx]
            # end maps to one past the last matched normalized char, back in origin
            end = index_map[nidx + len(norm_needle) - 1] + 1
            return LocatedSpan(start, end, "normalized", 99.0)

    # 3. fuzzy — score on lowercased text (length-preserving, so indices align)
    low_hay = haystack.lower()
    low_needle = needle.lower()
    score = fuzz.partial_ratio(low_needle, low_hay)
    if score < fuzzy_threshold:
        return None
    alignment = fuzz.partial_ratio_alignment(low_needle, low_hay)
    if alignment is None:
        return None
    return LocatedSpan(alignment.dest_start, alignment.dest_end, "fuzzy", float(score))
