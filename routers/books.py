from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from database import get_db
import models
import schemas
from utils.search import sanitize_search_query

router = APIRouter()

@router.get("", response_model=schemas.PaginatedBookResponse)
def list_books(
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    category_id: Optional[int] = None,
    language: Optional[str] = None,
    year: Optional[int] = None,
    author: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.Book).filter(models.Book.is_public == True)
    
    if category_id:
        query = query.filter(models.Book.category_id == category_id)
    if language:
        query = query.filter(models.Book.language.ilike(language))
    if year:
        query = query.filter(models.Book.publication_year == year)
    if author:
        query = query.join(models.Book.authors).filter(models.Author.name.ilike(f"%{author}%"))
        
    total_count = query.count()
    total_pages = (total_count + limit - 1) // limit

    offset = (page - 1) * limit
    books = query.order_by(desc(models.Book.created_at)).offset(offset).limit(limit).all()

    return schemas.PaginatedBookResponse(
        items=books,
        total_count=total_count,
        page=page,
        limit=limit,
        total_pages=total_pages
    )

@router.get("/featured", response_model=List[schemas.BookResponse])
def get_featured_books(limit: int = Query(6, ge=1, le=20), db: Session = Depends(get_db)):
    books = db.query(models.Book).filter(
        models.Book.is_public == True
    ).order_by(
        desc(models.Book.view_count), 
        desc(models.Book.created_at)
    ).limit(limit).all()
    return books

@router.get("/search", response_model=schemas.PaginatedBookResponse)
def search_books(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db)
):
    clean_query = sanitize_search_query(q)
    if not clean_query:
        return schemas.PaginatedBookResponse(items=[], total_count=0, page=page, limit=limit, total_pages=0)
        
    ts_query = func.plainto_tsquery("english", clean_query)
    rank = func.ts_rank_cd(models.Book.search_vector, ts_query)
    
    query = db.query(models.Book).filter(
        models.Book.is_public == True,
        models.Book.search_vector.op("@@")(ts_query)
    )

    total_count = query.count()
    total_pages = (total_count + limit - 1) // limit

    offset = (page - 1) * limit
    books = query.order_by(
        desc(rank),
        desc(models.Book.created_at)
    ).offset(offset).limit(limit).all()
    
    return schemas.PaginatedBookResponse(
        items=books,
        total_count=total_count,
        page=page,
        limit=limit,
        total_pages=total_pages
    )

@router.get("/categories", response_model=List[schemas.CategoryResponse])
def list_categories(db: Session = Depends(get_db)):
    return db.query(models.Category).all()

@router.get("/category/{slug}", response_model=schemas.PaginatedBookResponse)
def get_books_by_category(
    slug: str,
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db)
):
    category = db.query(models.Category).filter(models.Category.slug == slug).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
        
    subcategories = db.query(models.Category).filter(models.Category.parent_id == category.id).all()
    category_ids = [category.id] + [sub.id for sub in subcategories]
    
    query = db.query(models.Book).filter(
        models.Book.is_public == True,
        models.Book.category_id.in_(category_ids)
    )

    total_count = query.count()
    total_pages = (total_count + limit - 1) // limit

    offset = (page - 1) * limit
    books = query.order_by(desc(models.Book.created_at)).offset(offset).limit(limit).all()

    return schemas.PaginatedBookResponse(
        items=books,
        total_count=total_count,
        page=page,
        limit=limit,
        total_pages=total_pages
    )

@router.get("/{id}", response_model=schemas.BookDetailResponse)
def get_book_detail(id: int, db: Session = Depends(get_db)):
    book = db.query(models.Book).filter(models.Book.id == id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    reviews_with_usernames = []
    for r in book.reviews:
        reviews_with_usernames.append(
            schemas.ReviewResponse(
                id=r.id,
                user_id=r.user_id,
                book_id=r.book_id,
                rating=r.rating,
                comment=r.comment,
                created_at=r.created_at,
                username=r.user.username if r.user else "Anonymous"
            )
        )
        
    response = schemas.BookDetailResponse.from_orm(book)
    response.reviews = reviews_with_usernames
    return response

@router.post("/{id}/view", response_model=schemas.BookResponse)
def increment_view_count(id: int, db: Session = Depends(get_db)):
    book = db.query(models.Book).filter(models.Book.id == id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    book.view_count += 1
    db.commit()
    db.refresh(book)
    return book

@router.post("/{id}/download")
def increment_download_count(id: int, db: Session = Depends(get_db)):
    book = db.query(models.Book).filter(models.Book.id == id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    book.download_count += 1
    db.commit()
    db.refresh(book)
    return {"file_url": book.file_url, "download_count": book.download_count}
