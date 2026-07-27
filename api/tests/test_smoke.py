from app.db import Base
import app.models  # noqa: F401  (registers tables on Base.metadata)


def test_all_tables_registered():
    """Every table from plan.md §3 is mapped."""
    expected = {
        "sources",
        "contacts",
        "commitments",
        "evidence",
        "merges",
        "jobs",
        "llm_calls",
        "llm_cache",
    }
    assert expected.issubset(set(Base.metadata.tables))
