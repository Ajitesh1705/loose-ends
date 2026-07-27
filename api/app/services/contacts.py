"""Contact resolution. Phase 2/3: match an existing contact case-insensitively by
display name or alias, else create one. Richer alias/entity matching for dedupe is
Phase 4's job — kept deliberately simple here.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Contact


def get_or_create_contact(db: Session, name: str, hint: str | None = None) -> Contact:
    name = (name or "").strip()
    if not name and hint:
        name = hint.strip()
    if not name:
        name = "Unknown"

    lowered = name.lower()
    existing = db.scalar(
        select(Contact).where(func.lower(Contact.display_name) == lowered)
    )
    if existing:
        return existing

    # alias match: name = ANY(aliases)
    existing = db.scalar(select(Contact).where(Contact.aliases.any(name)))
    if existing:
        return existing

    contact = Contact(display_name=name, aliases=[])
    db.add(contact)
    db.flush()
    return contact
