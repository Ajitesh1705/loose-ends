from app.services.locate import locate_span

SOURCE = (
    "Priya: Thanks for hopping on.\n"
    "Me: Yeah I'll get the Q3 audience breakdown over to you before Friday, with "
    "the age and geo splits.\n"
    "Priya: Perfect."
)


def test_exact_match():
    quote = "I'll get the Q3 audience breakdown over to you before Friday"
    span = locate_span(SOURCE, quote)
    assert span is not None
    assert span.method == "exact"
    assert SOURCE[span.start : span.end] == quote


def test_normalized_whitespace_match():
    # Model re-flowed whitespace: newline/space runs collapsed to single spaces.
    quote = "get the Q3 audience breakdown   over to\nyou before Friday"
    span = locate_span(SOURCE, quote)
    assert span is not None
    assert span.method == "normalized"
    # The projected span still points at real source text.
    assert "Q3 audience breakdown" in SOURCE[span.start : span.end]


def test_case_insensitive_match():
    quote = "I'LL GET THE Q3 AUDIENCE BREAKDOWN OVER TO YOU BEFORE FRIDAY"
    span = locate_span(SOURCE, quote)
    assert span is not None
    assert span.method in {"normalized", "fuzzy"}


def test_fuzzy_match_small_typo():
    # A single-character typo the model introduced.
    quote = "I'll get the Q3 audiance breakdown over to you before Friday"
    span = locate_span(SOURCE, quote)
    assert span is not None
    assert span.method == "fuzzy"
    assert span.score >= 90


def test_unlocatable_returns_none():
    span = locate_span(SOURCE, "completely fabricated promise never in the source")
    assert span is None


def test_empty_needle_returns_none():
    assert locate_span(SOURCE, "   ") is None
