"""SQLModel payment note repository implementation."""

from pydantic_invoices.interfaces.payment_note_repo import PaymentNoteRepository
from pydantic_invoices.schemas.payment_note import (
    PaymentNote,
    PaymentNoteCreate,
)
from sqlmodel import Session, select

from .models import PaymentNoteDB


class SQLModelPaymentNoteRepository(PaymentNoteRepository):
    """Generic SQLModel implementation for PaymentNote repository."""

    def __init__(self, session: Session):
        """Initialize with SQLModel session."""
        self.session = session

    def create(self, data: PaymentNoteCreate) -> PaymentNote:
        """Create payment note in database."""
        db_note = PaymentNoteDB(**data.model_dump())
        self.session.add(db_note)
        self.session.commit()
        self.session.refresh(db_note)
        return db_note.to_schema()

    def get_by_id(self, note_id: int) -> PaymentNote | None:
        """Get payment note by ID."""
        db_note = self.session.get(PaymentNoteDB, note_id)
        return db_note.to_schema() if db_note else None

    def get_all(self, skip: int = 0, limit: int = 100) -> list[PaymentNote]:
        """Get all payment notes with pagination."""
        stmt = select(PaymentNoteDB).offset(skip).limit(limit)
        db_notes = self.session.exec(stmt).all()
        return [n.to_schema() for n in db_notes]

    def get_active(self, company_id: int | None = None) -> list[PaymentNote]:
        """Get all active payment notes."""
        stmt = select(PaymentNoteDB).where(PaymentNoteDB.is_active == True)  # noqa: E712
        if company_id:
            stmt = stmt.where(PaymentNoteDB.company_id == company_id)
        db_notes = self.session.exec(stmt).all()
        return [n.to_schema() for n in db_notes]

    def get_by_company(self, company_id: int | None = None) -> list[PaymentNote]:
        """Get payment notes for a specific company."""
        stmt = select(PaymentNoteDB).where(PaymentNoteDB.company_id == company_id)
        db_notes = self.session.exec(stmt).all()
        return [n.to_schema() for n in db_notes]

    def get_default(self, company_id: int | None = None) -> PaymentNote | None:
        """Get default payment note for a company."""
        stmt = select(PaymentNoteDB).where(PaymentNoteDB.is_default == True)  # noqa: E712
        if company_id:
            stmt = stmt.where(PaymentNoteDB.company_id == company_id)
        db_note = self.session.exec(stmt).first()
        return db_note.to_schema() if db_note else None

    def update(self, note: PaymentNote) -> PaymentNote:
        """Update payment note."""
        db_note = self.session.get(PaymentNoteDB, note.id)
        if not db_note:
            raise ValueError(f"PaymentNote {note.id} not found")

        for key, value in note.model_dump(exclude={"id"}).items():
            setattr(db_note, key, value)

        self.session.commit()
        self.session.refresh(db_note)
        return db_note.to_schema()

    def delete(self, note_id: int) -> bool:
        """Delete payment note."""
        db_note = self.session.get(PaymentNoteDB, note_id)
        if db_note:
            self.session.delete(db_note)
            self.session.commit()
            return True
        return False
