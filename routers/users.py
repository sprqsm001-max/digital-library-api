from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List
from database import get_db
import models
import schemas
from utils.auth import get_current_active_user

router = APIRouter()

@router.get("/bookmarks", response_model=List[schemas.BookmarkResponse])
def get_bookmarks(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    bookmarks = db.query(models.Bookmark).filter(
        models.Bookmark.user_id == current_user.id
    ).order_by(desc(models.Bookmark.saved_at)).all()
    return bookmarks

@router.post("/bookmarks/{book_id}", response_model=schemas.BookmarkResponse)
def add_bookmark(
    book_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Check if book exists
    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found"
        )
        
    bookmark = db.query(models.Bookmark).filter(
        models.Bookmark.user_id == current_user.id,
        models.Bookmark.book_id == book_id
    ).first()
    
    if not bookmark:
        bookmark = models.Bookmark(user_id=current_user.id, book_id=book_id)
        db.add(bookmark)
        db.commit()
        db.refresh(bookmark)
        
    return bookmark

@router.delete("/bookmarks/{book_id}")
def remove_bookmark(
    book_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    bookmark = db.query(models.Bookmark).filter(
        models.Bookmark.user_id == current_user.id,
        models.Bookmark.book_id == book_id
    ).first()
    
    if not bookmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bookmark not found"
        )
        
    db.delete(bookmark)
    db.commit()
    return {"detail": "Bookmark removed"}

@router.get("/history", response_model=List[schemas.ReadingHistoryResponse])
def get_history(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    history = db.query(models.ReadingHistory).filter(
        models.ReadingHistory.user_id == current_user.id
    ).order_by(desc(models.ReadingHistory.last_read_at)).all()
    return history

@router.post("/history/{book_id}", response_model=schemas.ReadingHistoryResponse)
def add_to_history(
    book_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found"
        )
        
    history = db.query(models.ReadingHistory).filter(
        models.ReadingHistory.user_id == current_user.id,
        models.ReadingHistory.book_id == book_id
    ).first()
    
    if history:
        history.read_count += 1
        history.last_read_at = func.now()
    else:
        history = models.ReadingHistory(user_id=current_user.id, book_id=book_id, read_count=1)
        db.add(history)
        
    db.commit()
    db.refresh(history)
    return history

@router.post("/reviews/{book_id}", response_model=schemas.ReviewResponse)
def submit_review(
    book_id: int,
    review_in: schemas.ReviewCreate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found"
        )
        
    review = db.query(models.Review).filter(
        models.Review.user_id == current_user.id,
        models.Review.book_id == book_id
    ).first()
    
    if review:
        review.rating = review_in.rating
        review.comment = review_in.comment
        review.created_at = func.now()
    else:
        review = models.Review(
            user_id=current_user.id,
            book_id=book_id,
            rating=review_in.rating,
            comment=review_in.comment
        )
        db.add(review)
        
    db.commit()
    db.refresh(review)
    
    # Construct response manually to inject username easily
    response = schemas.ReviewResponse.from_orm(review)
    response.username = current_user.username
    return response
