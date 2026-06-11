import os
import shutil
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from database import get_db
import models
import schemas
from utils.auth import require_admin
from utils.epub import extract_epub_metadata

router = APIRouter()

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/home/oldafric/public_html/uploads")

@router.post("/upload-book", response_model=dict)
async def upload_book_file(
    file: UploadFile = File(...),
    current_user: models.User = Depends(require_admin)
):
    if not file.filename.lower().endswith('.epub'):
        raise HTTPException(status_code=400, detail="Strict Requirement: Only .epub files are permitted.")

    file_extension = ".epub"
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, "books", unique_filename)

    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Automated Ingestion: Extract Metadata
    metadata = extract_epub_metadata(file_path)

    return {
        "filename": file.filename,
        "url": f"https://www.oldafricanbooks.com/uploads/books/{unique_filename}",
        "file_type": "epub",
        "file_size_kb": os.path.getsize(file_path) // 1024,
        "metadata": metadata
    }

@router.post("/upload-cover", response_model=dict)
async def upload_cover_image(
    file: UploadFile = File(...),
    current_user: models.User = Depends(require_admin)
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Only images allowed.")

    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, "covers", unique_filename)

    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "url": f"https://www.oldafricanbooks.com/uploads/covers/{unique_filename}"
    }

@router.post("/ingest", response_model=List[schemas.BookResponse])
async def ingest_epubs(
    files: List[UploadFile] = File(...),
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    \"\"\"
    Automated EPUB Ingestion System:
    Takes multiple EPUB files, extracts metadata, creates authors, and organizes them into the library.
    \"\"\"
    ingested_books = []

    for file in files:
        if not file.filename.lower().endswith('.epub'):
            continue

        # 1. Save File
        file_extension = ".epub"
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, "books", unique_filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. Extract Metadata
        metadata = extract_epub_metadata(file_path)

        # 3. Process Authors
        book_authors = []
        for name in metadata.get("authors", []):
            author = db.query(models.Author).filter(models.Author.name == name).first()
            if not author:
                author = models.Author(name=name)
                db.add(author)
                db.flush()
            book_authors.append(author)

        # 4. Create Book
        db_book = models.Book(
            title=metadata.get("title", file.filename),
            description=metadata.get("description", ""),
            file_url=f"https://www.oldafricanbooks.com/uploads/books/{unique_filename}",
            file_type="epub",
            file_size_kb=os.path.getsize(file_path) // 1024,
            language=metadata.get("language", "English"),
            publication_year=metadata.get("publication_year"),
            publisher=metadata.get("publisher"),
            isbn=metadata.get("isbn"),
            published_status="Live",
            is_public=True,
            uploaded_by=current_user.id
        )
        db_book.authors = book_authors
        db.add(db_book)
        ingested_books.append(db_book)

    db.commit()
    for b in ingested_books:
        db.refresh(b)

    return ingested_books

@router.post("/books", response_model=schemas.BookResponse, status_code=status.HTTP_201_CREATED)
def create_book(
    book_in: schemas.BookCreate,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    authors = []
    if book_in.author_ids:
        authors = db.query(models.Author).filter(models.Author.id.in_(book_in.author_ids)).all()
    if book_in.author_names:
        for name in book_in.author_names:
            author = db.query(models.Author).filter(models.Author.name == name).first()
            if not author:
                author = models.Author(name=name)
                db.add(author)
                db.flush()
            if author not in authors:
                authors.append(author)

    db_book = models.Book(
        title=book_in.title,
        subtitle=book_in.subtitle,
        description=book_in.description,
        cover_image_url=book_in.cover_image_url,
        file_url=book_in.file_url,
        file_type="epub",
        file_size_kb=book_in.file_size_kb,
        language=book_in.language,
        publication_year=book_in.publication_year,
        publisher=book_in.publisher,
        isbn=book_in.isbn,
        published_status=book_in.published_status,
        target_audience=book_in.target_audience,
        reading_level=book_in.reading_level,
        content_advisory=book_in.content_advisory,
        category_id=book_in.category_id,
        tags=book_in.tags,
        is_public=book_in.is_public,
        uploaded_by=current_user.id
    )
    db_book.authors = authors

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
        raise HTTPException(status_code=404, detail="Book not found")
        
    update_data = book_in.dict(exclude_unset=True)
    if "author_ids" in update_data:
        author_ids = update_data.pop("author_ids")
        authors = db.query(models.Author).filter(models.Author.id.in_(author_ids)).all()
        db_book.authors = authors

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
        raise HTTPException(status_code=404, detail="Book not found")
    db.delete(db_book)
    db.commit()
    return {"detail": "Book successfully deleted"}

@router.get("/stats", response_model=schemas.AdminStats)
def get_stats(
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    total_books = db.query(models.Book).count()
    total_authors = db.query(models.Author).count()
    total_users = db.query(models.User).count()
    total_reviews = db.query(models.Review).count()
    total_views = db.query(func.sum(models.Book.view_count)).scalar() or 0
    total_downloads = db.query(func.sum(models.Book.download_count)).scalar() or 0
    return schemas.AdminStats(
        total_books=total_books,
        total_authors=total_authors,
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
        raise HTTPException(status_code=400, detail="Category name or slug already exists")
    db_category = models.Category(**category_in.dict())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@router.get("/users", response_model=List[schemas.UserResponse])
def list_users(
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    return db.query(models.User).order_by(desc(models.User.created_at)).all()

@router.post("/authors", response_model=schemas.AuthorResponse, status_code=status.HTTP_201_CREATED)
def create_author(
    author_in: schemas.AuthorCreate,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    db_author = models.Author(**author_in.dict())
    db.add(db_author)
    db.commit()
    db.refresh(db_author)
    return db_author

@router.get("/authors", response_model=List[schemas.AuthorResponse])
def list_authors(
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    return db.query(models.Author).order_by(models.Author.name).all()
