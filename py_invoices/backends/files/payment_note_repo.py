"""File-based payment note repository."""

from pathlib import Path

from pydantic_invoices.interfaces import PaymentNoteRepository
from pydantic_invoices.schemas.payment_note import PaymentNote, PaymentNoteCreate

from .storage import FileStorage


class FilePaymentNoteRepository(PaymentNoteRepository):
    """File-based implementation of PaymentNoteRepository."""

    def __init__(self, root_dir: str | Path, file_format: str = "json") -> None:
        """Initialize file repository."""
        self.storage = FileStorage[PaymentNote](
            root_dir, "payment_notes", PaymentNote, default_format=file_format
        )

    def create(self, data: PaymentNoteCreate) -> PaymentNote:
        """Create a new payment note."""
        note_id = self.storage.get_next_id()
        note = PaymentNote(id=note_id, **data.model_dump())
        self.storage.save(note, note_id)
        return note

    def get_by_id(self, note_id: int) -> PaymentNote | None:
        """Get payment note by ID."""
        return self.storage.load(note_id)

    def get_all(self, skip: int = 0, limit: int = 100) -> list[PaymentNote]:
        """Get all payment notes with pagination."""
        notes = self.storage.load_all()
        return notes[skip : skip + limit]

    def get_active(self, company_id: int | None = None) -> list[PaymentNote]:
        """Get active payment notes."""
        return [
            n
            for n in self.storage.load_all()
            if n.is_active and (company_id is None or n.company_id == company_id)
        ]

    def get_by_company(self, company_id: int | None = None) -> list[PaymentNote]:
        """Get all payment notes for a company."""
        return [note for note in self.storage.load_all() if note.company_id == company_id]

    def get_default(self, company_id: int | None = None) -> PaymentNote | None:
        """Get default payment note."""
        for n in self.storage.load_all():
            if n.is_default and n.is_active and (company_id is None or n.company_id == company_id):
                return n
        return None

    def update(self, note: PaymentNote) -> PaymentNote:
        """Update payment note."""
        existing = self.storage.load(note.id)
        if not existing:
            raise ValueError(f"PaymentNote {note.id} not found")

        self.storage.save(note, note.id)
        return note

    def delete(self, note_id: int) -> bool:
        """Delete payment note."""
        return self.storage.delete(note_id)
