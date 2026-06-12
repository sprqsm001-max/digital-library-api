from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List
from pydantic import BaseModel
import os
import re
import uuid
from database import get_db
import models
import schemas
from utils.auth import require_admin
from utils.epub_parser import parse_epub_metadata

# Upload paths relative to the project root where main.py resides
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
UPLOAD_DIR = os.path.join(STATIC_DIR, "uploads", "books")
COVER_DIR = os.path.join(STATIC_DIR, "uploads", "covers")

# Make sure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(COVER_DIR, exist_ok=True)

def make_slug(name: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", name).lower()
    return re.sub(r"[-\s_]+", "-", cleaned).strip("-")

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

@router.post("/books/upload-epub", status_code=status.HTTP_201_CREATED)
async def upload_epub_books(
    files: List[UploadFile] = File(...),
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    results = []
    errors = []
    
    for file in files:
        if not file.filename.lower().endswith(".epub"):
            errors.append({"filename": file.filename, "error": "Only .epub files are supported"})
            continue
            
        try:
            contents = await file.read()
            epub_data = parse_epub_metadata(contents)
            if not epub_data:
                errors.append({"filename": file.filename, "error": "Failed to parse EPUB metadata"})
                continue
                
            # Check if book already exists
            existing_book = db.query(models.Book).filter(
                models.Book.title.ilike(epub_data["title"]),
                models.Book.author.ilike(epub_data["author"])
            ).first()
            if existing_book:
                errors.append({"filename": file.filename, "error": f"Book '{epub_data['title']}' by {epub_data['author']} already exists"})
                continue
                
            # Category selection
            category_id = None
            subjects = epub_data.get("subjects", [])
            db_cat = None
            if subjects:
                primary_subject = subjects[0]
                cat_slug = make_slug(primary_subject)
                db_cat = db.query(models.Category).filter(
                    (models.Category.slug == cat_slug) | (models.Category.name.ilike(primary_subject))
                ).first()
                if not db_cat:
                    db_cat = models.Category(
                        name=primary_subject,
                        slug=cat_slug,
                        description=f"Books related to {primary_subject}"
                    )
                    db.add(db_cat)
                    db.commit()
                    db.refresh(db_cat)
                category_id = db_cat.id
            else:
                db_cat = db.query(models.Category).filter(models.Category.slug == "uncategorized").first()
                if not db_cat:
                    db_cat = models.Category(
                        name="Uncategorized",
                        slug="uncategorized",
                        description="Books without a specific subject category"
                    )
                    db.add(db_cat)
                    db.commit()
                    db.refresh(db_cat)
                category_id = db_cat.id
                
            # Save files
            unique_id = str(uuid.uuid4())
            safe_title = make_slug(epub_data["title"]) or "book"
            
            # Save EPUB
            epub_filename = f"{safe_title}_{unique_id}.epub"
            epub_filepath = os.path.join(UPLOAD_DIR, epub_filename)
            with open(epub_filepath, "wb") as f:
                f.write(contents)
                
            # Save cover
            cover_image_url = None
            if epub_data.get("cover_image_bytes"):
                mime = epub_data.get("cover_image_type", "")
                ext = ".jpg"
                if "png" in mime:
                    ext = ".png"
                elif "gif" in mime:
                    ext = ".gif"
                cover_filename = f"{safe_title}_{unique_id}{ext}"
                cover_filepath = os.path.join(COVER_DIR, cover_filename)
                with open(cover_filepath, "wb") as f:
                    f.write(epub_data["cover_image_bytes"])
                cover_image_url = f"/static/uploads/covers/{cover_filename}"
                
            file_url = f"/static/uploads/books/{epub_filename}"
            file_size_kb = len(contents) // 1024
            
            # Create Book DB record
            db_book = models.Book(
                title=epub_data["title"],
                author=epub_data["author"],
                description=epub_data["description"] or f"Ebook copy of {epub_data['title']}.",
                cover_image_url=cover_image_url,
                file_url=file_url,
                file_type="epub",
                file_size_kb=file_size_kb,
                language=epub_data["language"] or "English",
                publication_year=epub_data["publication_year"],
                publisher=epub_data["publisher"],
                isbn=epub_data["isbn"],
                category_id=category_id,
                tags=subjects,
                is_public=True,
                uploaded_by=current_user.id,
                content_text=epub_data["content_text"]
            )
            db.add(db_book)
            db.commit()
            db.refresh(db_book)
            
            results.append({
                "id": db_book.id,
                "title": db_book.title,
                "author": db_book.author,
                "category_id": db_book.category_id,
                "category_name": db_cat.name if db_cat else "Uncategorized",
                "cover_image_url": db_book.cover_image_url,
                "file_url": db_book.file_url,
                "file_size_kb": db_book.file_size_kb,
                "language": db_book.language,
                "publication_year": db_book.publication_year,
                "publisher": db_book.publisher,
                "isbn": db_book.isbn,
                "tags": db_book.tags,
                "created_at": db_book.created_at.isoformat() if db_book.created_at else None
            })
        except Exception as e:
            errors.append({"filename": file.filename, "error": str(e)})
            
    return {"uploaded": results, "errors": errors}


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
