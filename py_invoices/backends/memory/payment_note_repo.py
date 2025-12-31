"""In-memory payment note repository."""

from pydantic_invoices.interfaces import PaymentNoteRepository  # type: ignore[import-untyped]
from pydantic_invoices.schemas.payment_note import (  # type: ignore[import-untyped]
    PaymentNote,
    PaymentNoteCreate,
)


class MemoryPaymentNoteRepository(PaymentNoteRepository):  # type: ignore[misc]
    """In-memory implementation for PaymentNote repository."""

    def __init__(self) -> None:
        """Initialize with empty storage."""
        self._storage: dict[int, PaymentNote] = {}
        self._next_id = 1

    def create(self, data: PaymentNoteCreate) -> PaymentNote:
        """Create payment note."""
        note = PaymentNote(id=self._next_id, **data.model_dump())
        self._storage[self._next_id] = note
        self._next_id += 1
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

    def get_by_company(self, company_id: int) -> list[PaymentNote]:
        """Get payment notes for a company."""
        return [n for n in self._storage.values() if n.company_id == company_id]

    def get_default(self, company_id: int | None = None) -> PaymentNote | None:
        """Get default payment note."""
        for note in self._storage.values():
            if note.is_default:
                if company_id is None or note.company_id == company_id:
                    return note
        return None

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
