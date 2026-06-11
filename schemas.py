from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str
    user: Optional[dict] = None

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
        orm_mode = True

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
        orm_mode = True

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
    username: Optional[str] = None  # Add username helper for frontend reviews

    class Config:
        from_attributes = True
        orm_mode = True

# Book schemas
class BookBase(BaseModel):
    title: str
    author: Optional[str] = None
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    file_url: Optional[str] = None
    file_type: Optional[str] = None
    file_size_kb: Optional[int] = None
    language: Optional[str] = "English"
    publication_year: Optional[int] = None
    publisher: Optional[str] = None
    isbn: Optional[str] = None
    category_id: Optional[int] = None
    tags: Optional[List[str]] = []
    is_public: Optional[bool] = True

class BookCreate(BookBase):
    pass

class BookUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    file_url: Optional[str] = None
    file_type: Optional[str] = None
    file_size_kb: Optional[int] = None
    language: Optional[str] = None
    publication_year: Optional[int] = None
    publisher: Optional[str] = None
    isbn: Optional[str] = None
    category_id: Optional[int] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None

class BookResponse(BookBase):
    id: int
    download_count: int
    view_count: int
    uploaded_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        orm_mode = True

class BookDetailResponse(BookResponse):
    category: Optional[CategoryResponse] = None
    reviews: List[ReviewResponse] = []

    class Config:
        from_attributes = True
        orm_mode = True

# Bookmark schemas
class BookmarkResponse(BaseModel):
    id: int
    user_id: int
    book_id: int
    saved_at: datetime
    book: Optional[BookResponse] = None

    class Config:
        from_attributes = True
        orm_mode = True

# Reading History schemas
class ReadingHistoryResponse(BaseModel):
    id: int
    user_id: int
    book_id: int
    last_read_at: datetime
    read_count: int
    book: Optional[BookResponse] = None

    class Config:
        from_attributes = True
        orm_mode = True

# Admin stats schema
class AdminStats(BaseModel):
    total_books: int
    total_users: int
    total_downloads: int
    total_views: int
    total_reviews: int
