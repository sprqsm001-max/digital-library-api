from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, Table, DateTime, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String(20), default="reader")  # reader, librarian, admin
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)

    # Relationships
    uploaded_books = relationship("Book", back_populates="uploader")
    bookmarks = relationship("Bookmark", back_populates="user", cascade="all, delete-orphan")
    reading_history = relationship("ReadingHistory", back_populates="user", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="user", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text)
    parent_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    parent = relationship("Category", remote_side=[id], backref="subcategories")
    books = relationship("Book", back_populates="category")


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False, index=True)
    author = Column(String(300), index=True)
    description = Column(Text)
    cover_image_url = Column(Text, nullable=True)
    file_url = Column(Text, nullable=True)
    file_type = Column(String(20))  # pdf, epub, txt
    file_size_kb = Column(Integer)
    language = Column(String(50), default="English")
    publication_year = Column(Integer)
    publisher = Column(String(200))
    isbn = Column(String(50))
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    tags = Column(ARRAY(String), nullable=True)
    is_public = Column(Boolean, default=True)
    download_count = Column(Integer, default=0)
    view_count = Column(Integer, default=0)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    content_text = Column(Text, nullable=True)


    # FTS Column mapped as read-only (since it is maintained by database trigger)
    search_vector = Column(TSVECTOR, index=False, nullable=True)

    # Relationships
    uploader = relationship("User", back_populates="uploaded_books")
    category = relationship("Category", back_populates="books")
    bookmarks = relationship("Bookmark", back_populates="book", cascade="all, delete-orphan")
    reading_history = relationship("ReadingHistory", back_populates="book", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="book", cascade="all, delete-orphan")


class ReadingHistory(Base):
    __tablename__ = "reading_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    last_read_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    read_count = Column(Integer, default=1)

    # Relationships
    user = relationship("User", back_populates="reading_history")
    book = relationship("Book", back_populates="reading_history")


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    saved_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="bookmarks")
    book = relationship("Book", back_populates="bookmarks")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1 to 5
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="reviews")
    book = relationship("Book", back_populates="reviews")
