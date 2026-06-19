import sqlalchemy as sq
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base, IdMixin, generate_snowflake_id


class Note(Base, IdMixin):
    __tablename__ = "notes"

    title: Mapped[str] = mapped_column(sq.String(255), nullable=False)
    content: Mapped[str] = mapped_column(sq.Text, nullable=False, default="")
    created_at: Mapped[sq.DateTime] = mapped_column(
        sq.DateTime(timezone=True),
        nullable=False,
        server_default=sq.func.now(),
    )
    updated_at: Mapped[sq.DateTime] = mapped_column(
        sq.DateTime(timezone=True),
        nullable=False,
        server_default=sq.func.now(),
        onupdate=sq.func.now(),
    )

    def __init__(self, title: str, content: str = "") -> None:
        self._id = generate_snowflake_id()
        self.title = title
        self.content = content

    @staticmethod
    def _mock(note_id: int = 1) -> "Note":
        note = Note(title=f"Test Note {note_id}", content="Mock content")
        note._id = note_id
        return note
