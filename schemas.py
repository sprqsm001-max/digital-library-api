from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import List, Optional
from datetime import datetime

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[int] = None
    role: Optional[str] = None

# User schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Author schemas
class AuthorBase(BaseModel):
    name: str
    biography: Optional[str] = None

class AuthorCreate(AuthorBase):
    pass

class AuthorResponse(AuthorBase):
    id: int

    class Config:
        from_attributes = True

# Category schemas
class CategoryBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    parent_id: Optional[int] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int

    class Config:
        from_attributes = True

# Review schemas
class ReviewBase(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None

class ReviewCreate(ReviewBase):
    pass

class ReviewResponse(ReviewBase):
    id: int
    user_id: int
    book_id: int
    created_at: datetime
    username: Optional[str] = None

    class Config:
        from_attributes = True

# Book schemas
class BookBase(BaseModel):
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    file_url: Optional[str] = None  # Made optional for legacy data
    file_type: Optional[str] = "epub"
    file_size_kb: Optional[int] = None
    language: Optional[str] = "English"
    publication_year: Optional[int] = None
    publisher: Optional[str] = None
    isbn: Optional[str] = None
    published_status: Optional[str] = "Draft"

    # Categorization Taxonomies - made optional for legacy data
    target_audience: Optional[List[str]] = []
    reading_level: Optional[str] = None
    content_advisory: Optional[List[str]] = []

    category_id: Optional[int] = None
    tags: Optional[List[str]] = []
    is_public: bool = True

    @field_validator('target_audience', 'content_advisory', 'tags', mode='before')
    @classmethod
    def ensure_list(cls, v):
        if v is None:
            return []
        return v

class BookCreate(BookBase):
    author_ids: List[int] = []
    author_names: List[str] = []

class BookUpdate(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    file_url: Optional[str] = None
    file_type: Optional[str] = None
    file_size_kb: Optional[int] = None
    language: Optional[str] = None
    publication_year: Optional[int] = None
    publisher: Optional[str] = None
    isbn: Optional[str] = None
    published_status: Optional[str] = None
    target_audience: Optional[List[str]] = None
    reading_level: Optional[str] = None
    content_advisory: Optional[List[str]] = None
    category_id: Optional[int] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None
    author_ids: Optional[List[int]] = None

class BookResponse(BookBase):
    id: int
    authors: List[AuthorResponse] = []
    download_count: int = 0
    view_count: int = 0
    uploaded_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class BookDetailResponse(BookResponse):
    category: Optional[CategoryResponse] = None
    reviews: List[ReviewResponse] = []

    class Config:
        from_attributes = True

# Bookmark schemas
class BookmarkResponse(BaseModel):
    id: int
    user_id: int
    book_id: int
    saved_at: datetime
    book: Optional[BookResponse] = None

    class Config:
        from_attributes = True

# Reading History schemas
class ReadingHistoryResponse(BaseModel):
    id: int
    user_id: int
    book_id: int
    last_read_at: datetime
    read_count: int
    progress_percent: int = 0
    book: Optional[BookResponse] = None

    class Config:
        from_attributes = True

# Admin stats schema
class AdminStats(BaseModel):
    total_books: int
    total_authors: int
    total_users: int
    total_downloads: int
    total_views: int
    total_reviews: int

# Profile Update schemas
class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None

# Paginated Response schemas
class PaginatedBookResponse(BaseModel):
    items: List[BookResponse]
    total_count: int
    page: int
    limit: int
    total_pages: int

# Ingestion specific
class IngestResponse(BaseModel):
    success: bool
    message: str
    book_id: Optional[int] = None
    metadata: Optional[dict] = None
