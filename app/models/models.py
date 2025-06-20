from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.enums import PromptSource, StoryboardStatus


class CharacterArc(Base):
    __tablename__ = "character_arcs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(Text, nullable=False)  # Deprecated - Keeping for backward compatibility
    content_json = Column("content_json", JSON, nullable=True)
    type = Column(Text, nullable=False)
    source_id = Column(Integer, nullable=True)
    name = Column(Text, nullable=True)
    role = Column(Text, nullable=True)
    archetype = Column(Text, nullable=True)


class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)
    mime_type = Column(String(100))
    data = Column(LargeBinary)
    external_url = Column(Text, nullable=True)  # Store the original external URL
    created_at = Column(BigInteger, nullable=False)  # Unix timestamp
    updated_at = Column(BigInteger, nullable=False)  # Unix timestamp
    created_by = Column(String(255), nullable=False)  # User ID
    updated_by = Column(String(255), nullable=False)  # User ID


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), index=True)
    author = Column(String(255))
    author_id = Column(String(255), nullable=False)  # Auth0 user ID of the book creator
    cover_url = Column(Text, nullable=True)  # URL to the generated book cover
    created_at = Column(BigInteger, nullable=False)  # Unix timestamp
    updated_at = Column(BigInteger, nullable=False)  # Unix timestamp
    created_by = Column(String(255), nullable=False)  # User ID
    updated_by = Column(String(255), nullable=False)  # User ID
    chapters = relationship("Chapter", back_populates="book")


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    title = Column(Text, nullable=False)
    chapter_no = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    source_text = Column(Text, nullable=True)
    character_ids = Column(JSON, nullable=True, default=list)
    state = Column(String(50), default="DRAFT", nullable=False)
    created_at = Column(BigInteger, nullable=False)  # Unix timestamp
    updated_at = Column(BigInteger, nullable=False)  # Unix timestamp
    created_by = Column(String(255), nullable=False)  # User ID
    updated_by = Column(String(255), nullable=False)  # User ID
    book = relationship("Book", back_populates="chapters")
    scenes = relationship("Scene", back_populates="chapter")


class Character(Base):
    __tablename__ = "characters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)
    description = Column(Text)
    book_id = Column(Integer, ForeignKey("books.id"))
    created_at = Column(BigInteger, nullable=False)  # Unix timestamp
    updated_at = Column(BigInteger, nullable=False)  # Unix timestamp
    created_by = Column(String(255), nullable=False)  # User ID
    updated_by = Column(String(255), nullable=False)  # User ID


class Scene(Base):
    __tablename__ = "scenes"

    id = Column(Integer, primary_key=True, index=True)
    scene_number = Column(Integer)
    title = Column(String(255), index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"))
    content = Column(Text)
    created_at = Column(BigInteger, nullable=False)  # Unix timestamp
    updated_at = Column(BigInteger, nullable=False)  # Unix timestamp
    created_by = Column(String(255), nullable=False)  # User ID
    updated_by = Column(String(255), nullable=False)  # User ID
    chapter = relationship("Chapter", back_populates="scenes")


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), unique=True, index=True)
    title = Column(String(255), nullable=True)  # User-friendly title
    section = Column(String(100), nullable=True)  # Grouping category for settings
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    type = Column(String(50), nullable=False, default="string")  # string or list
    options = Column(Text, nullable=True)  # JSON string of options


class PlotBeat(Base):
    __tablename__ = "plot_beats"
    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(Text, nullable=False)
    type = Column(Text, nullable=False)
    source_id = Column(Integer, nullable=True)
    character_ids = Column(JSON, nullable=True, default=list)


class Template(Base):
    __tablename__ = "templates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    book_id = Column(Integer, nullable=False)
    summary_status = Column(Text, nullable=True)
    character_arc_status = Column(Text, nullable=True)
    plot_beats_status = Column(Text, nullable=True)
    character_arc_template_status = Column(Text, nullable=True)
    plot_beat_template_status = Column(Text, nullable=True)


class Storyboard(Base):
    __tablename__ = "storyboards"
    id = Column(Integer, primary_key=True, autoincrement=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=True)
    prompt = Column(Text, nullable=True)
    status = Column(Enum(StoryboardStatus), default=StoryboardStatus.NOT_STARTED)
    created_at = Column(BigInteger, nullable=False)  # Unix timestamp
    updated_at = Column(BigInteger, nullable=False)  # Unix timestamp
    created_by = Column(String(255), nullable=False)  # User ID
    updated_by = Column(String(255), nullable=False)  # User ID


class Prompt(Base):
    __tablename__ = "prompts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    source = Column(Enum(PromptSource), nullable=False)
    created_at = Column(BigInteger, nullable=False)  # Unix timestamp
    updated_at = Column(BigInteger, nullable=False)  # Unix timestamp
    created_by = Column(String(255), nullable=False)  # User ID
    updated_by = Column(String(255), nullable=False)  # User ID
