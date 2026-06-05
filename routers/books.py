from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from database import get_db
import models
import schemas
from utils.search import sanitize_search_query

router = APIRouter()

@router.get("", response_model=List[schemas.BookResponse])
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
        query = query.filter(models.Book.author.ilike(f"%{author}%"))
        
    offset = (page - 1) * limit
    books = query.order_by(desc(models.Book.created_at)).offset(offset).limit(limit).all()
    return books

@router.get("/featured", response_model=List[schemas.BookResponse])
def get_featured_books(limit: int = Query(6, ge=1, le=20), db: Session = Depends(get_db)):
    # Featured books are either high view count or most recently uploaded
    books = db.query(models.Book).filter(
        models.Book.is_public == True
    ).order_by(
        desc(models.Book.view_count), 
        desc(models.Book.created_at)
    ).limit(limit).all()
    return books

@router.get("/search", response_model=List[schemas.BookResponse])
def search_books(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db)
):
    clean_query = sanitize_search_query(q)
    if not clean_query:
        return []
        
    # PostgreSQL FTS plainto_tsquery search query
    ts_query = func.plainto_tsquery("english", clean_query)
    
    # Order results by relevance score (ts_rank_cd)
    rank = func.ts_rank_cd(models.Book.search_vector, ts_query)
    
    offset = (page - 1) * limit
    books = db.query(models.Book).filter(
        models.Book.is_public == True,
        models.Book.search_vector.op("@@")(ts_query)
    ).order_by(
        desc(rank),
        desc(models.Book.created_at)
    ).offset(offset).limit(limit).all()
    
    return books

@router.get("/category/{slug}", response_model=List[schemas.BookResponse])
def get_books_by_category(
    slug: str,
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db)
):
    category = db.query(models.Category).filter(models.Category.slug == slug).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
        
    # Retrieve books matching this category or its subcategories
    subcategories = db.query(models.Category).filter(models.Category.parent_id == category.id).all()
    category_ids = [category.id] + [sub.id for sub in subcategories]
    
    offset = (page - 1) * limit
    books = db.query(models.Book).filter(
        models.Book.is_public == True,
        models.Book.category_id.in_(category_ids)
    ).order_by(
        desc(models.Book.created_at)
    ).offset(offset).limit(limit).all()
    
    return books

@router.get("/{id}", response_model=schemas.BookDetailResponse)
def get_book_detail(id: int, db: Session = Depends(get_db)):
    book = db.query(models.Book).filter(models.Book.id == id).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found"
        )
    
    # We construct a detailed response with category and reviews (mapped to usernames)
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found"
        )
    book.view_count += 1
    db.commit()
    db.refresh(book)
    return book

@router.post("/{id}/download")
def increment_download_count(id: int, db: Session = Depends(get_db)):
    book = db.query(models.Book).filter(models.Book.id == id).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found"
        )
    book.download_count += 1
    db.commit()
    db.refresh(book)
    return {"file_url": book.file_url, "download_count": book.download_count}
