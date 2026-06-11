from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List
from pydantic import BaseModel
from database import get_db
import models
import schemas
from utils.auth import require_admin

router = APIRouter()

@router.post("/books", response_model=schemas.BookResponse, status_code=status.HTTP_201_CREATED)
def create_book(
    book_in: schemas.BookCreate,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    db_book = models.Book(
        title=book_in.title,
        author=book_in.author,
        description=book_in.description,
        cover_image_url=book_in.cover_image_url,
        file_url=book_in.file_url,
        file_type=book_in.file_type,
        file_size_kb=book_in.file_size_kb,
        language=book_in.language,
        publication_year=book_in.publication_year,
        publisher=book_in.publisher,
        isbn=book_in.isbn,
        category_id=book_in.category_id,
        tags=book_in.tags,
        is_public=book_in.is_public,
        uploaded_by=current_user.id
    )
    db.add(db_book)
    db.commit()
    db.refresh(db_book)
    return db_book

@router.put("/books/{id}", response_model=schemas.BookResponse)
def update_book(
    id: int,
    book_in: schemas.BookUpdate,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    db_book = db.query(models.Book).filter(models.Book.id == id).first()
    if not db_book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found"
        )
        
    update_data = book_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_book, key, value)
        
    db.commit()
    db.refresh(db_book)
    return db_book

@router.delete("/books/{id}")
def delete_book(
    id: int,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    db_book = db.query(models.Book).filter(models.Book.id == id).first()
    if not db_book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found"
        )
        
    db.delete(db_book)
    db.commit()
    return {"detail": "Book successfully deleted"}

@router.get("/stats", response_model=schemas.AdminStats)
def get_stats(
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    total_books = db.query(models.Book).count()
    total_users = db.query(models.User).count()
    total_reviews = db.query(models.Review).count()
    
    total_views = db.query(func.sum(models.Book.view_count)).scalar() or 0
    total_downloads = db.query(func.sum(models.Book.download_count)).scalar() or 0
    
    return schemas.AdminStats(
        total_books=total_books,
        total_users=total_users,
        total_downloads=total_downloads,
        total_views=total_views,
        total_reviews=total_reviews
    )

@router.post("/categories", response_model=schemas.CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    category_in: schemas.CategoryCreate,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    existing = db.query(models.Category).filter(
        (models.Category.name == category_in.name) | (models.Category.slug == category_in.slug)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category name or slug already exists"
        )
        
    db_category = models.Category(
        name=category_in.name,
        slug=category_in.slug,
        description=category_in.description,
        parent_id=category_in.parent_id
    )
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@router.get("/users", response_model=List[schemas.UserResponse])
def list_users(
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    users = db.query(models.User).order_by(desc(models.User.created_at)).all()
    return users


class RoleUpdate(BaseModel):
    role: str  # 'reader', 'librarian', 'admin'


@router.put("/users/{id}/role", response_model=schemas.UserResponse)
def update_user_role(
    id: int,
    role_in: RoleUpdate,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Promote or demote a user's role (admin only)."""
    valid_roles = ["reader", "librarian", "admin"]
    if role_in.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {valid_roles}"
        )
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    # Prevent self-demotion
    if user.id == current_user.id and role_in.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot demote your own admin account"
        )
    user.role = role_in.role
    db.commit()
    db.refresh(user)
    return user


@router.put("/users/{id}/toggle", response_model=schemas.UserResponse)
def toggle_user_active(
    id: int,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Activate or deactivate a user account (admin only)."""
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account"
        )
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    return user
