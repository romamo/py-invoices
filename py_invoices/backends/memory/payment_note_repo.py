"""In-memory payment note repository."""


from pydantic_invoices.interfaces.payment_note_repo import PaymentNoteRepository
from pydantic_invoices.schemas.payment_note import (
    PaymentNote,
    PaymentNoteCreate,
)


class MemoryPaymentNoteRepository(PaymentNoteRepository):
    """In-memory implementation of PaymentNoteRepository for testing."""

    def __init__(self) -> None:
        """Initialize with empty storage."""
        self._storage: dict[int, PaymentNote] = {}

    def create(self, entity: PaymentNoteCreate) -> PaymentNote:
        """Create a new payment note."""
        note_id = len(self._storage) + 1
        note_id = len(self._storage) + 1

        note = PaymentNote(
            id=note_id,
            title=entity.title,
            content=entity.content,
            company_id=entity.company_id,
            is_active=entity.is_active,
            is_default=entity.is_default,
            display_order=entity.display_order,
        )
        self._storage[note_id] = note
        return note

    def get_by_id(self, note_id: int) -> PaymentNote | None:
        """Get payment note by ID."""
        return self._storage.get(note_id)

    def get_all(self, skip: int = 0, limit: int = 100) -> list[PaymentNote]:
        """Get all payment notes."""
        return list(self._storage.values())[skip : skip + limit]

    def get_active(self, company_id: int | None = None) -> list[PaymentNote]:
        """Get active payment notes."""
        return [
            n for n in self._storage.values()
            if n.is_active and (company_id is None or n.company_id == company_id)
        ]

    def get_by_company(self, company_id: int | None = None) -> list[PaymentNote]:
        """Get all payment notes for a company."""
        return [
            note
            for note in self._storage.values()
            if note.company_id == company_id
        ]

    def get_default(self, company_id: int | None = None) -> PaymentNote | None:
        """Get default payment note."""
        return next(
            (
                n
                for n in self._storage.values()
                if n.is_default
                and n.is_active
                and (company_id is None or n.company_id == company_id)
            ),
            None,
        )

    def update(self, note: PaymentNote) -> PaymentNote:
        """Update payment note."""
        if note.id not in self._storage:
            raise ValueError(f"PaymentNote {note.id} not found")
        self._storage[note.id] = note
        return note

    def delete(self, note_id: int) -> bool:
        """Delete payment note."""
        if note_id in self._storage:
            del self._storage[note_id]
            return True
        return False
