from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func
from typing import List, Optional
from database import get_db
import models
import schemas
from utils.auth import get_current_active_user
from pydantic import BaseModel

router = APIRouter()

class ProgressUpdate(BaseModel):
    progress_percent: Optional[int] = None

# ─── Bookmarks ────────────────────────────────────────────────────────────────

@router.get("/bookmarks")
def get_bookmarks(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    bookmarks = db.query(models.Bookmark).options(
        joinedload(models.Bookmark.book)
    ).filter(
        models.Bookmark.user_id == current_user.id
    ).order_by(desc(models.Bookmark.saved_at)).all()

    result = []
    for bm in bookmarks:
        book = bm.book
        result.append({
            "id": bm.id,
            "user_id": bm.user_id,
            "book_id": bm.book_id,
            "saved_at": bm.saved_at,
            "title": book.title if book else None,
            "author": book.author if book else None,
            "cover_image_url": book.cover_image_url if book else None,
            "category_name": None,  # Could join category if needed
        })
    return result


@router.post("/bookmarks/{book_id}")
def add_bookmark(
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

    bookmark = db.query(models.Bookmark).filter(
        models.Bookmark.user_id == current_user.id,
        models.Bookmark.book_id == book_id
    ).first()

    if not bookmark:
        bookmark = models.Bookmark(user_id=current_user.id, book_id=book_id)
        db.add(bookmark)
        db.commit()
        db.refresh(bookmark)

    return {"id": bookmark.id, "user_id": bookmark.user_id, "book_id": bookmark.book_id, "saved_at": bookmark.saved_at}


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


# ─── Reading History ──────────────────────────────────────────────────────────

@router.get("/history")
def get_history(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    history = db.query(models.ReadingHistory).options(
        joinedload(models.ReadingHistory.book)
    ).filter(
        models.ReadingHistory.user_id == current_user.id
    ).order_by(desc(models.ReadingHistory.last_read_at)).all()

    result = []
    for h in history:
        book = h.book
        if not book:
            continue  # Skip orphaned history records (book was deleted)
        result.append({
            "id": h.id,
            "user_id": h.user_id,
            "book_id": h.book_id,
            "last_read": h.last_read_at.isoformat() if h.last_read_at else None,
            "read_count": h.read_count,
            "progress_percent": h.progress_percent or 0,
            # Flattened book fields so shelf.html can access directly
            "title": book.title,
            "author": book.author or "Unknown",
            "cover_image_url": book.cover_image_url,
            "category_name": None,
        })
    return result


@router.post("/history/{book_id}")
def update_history(
    book_id: int,
    body: ProgressUpdate = ProgressUpdate(),
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
        if body.progress_percent is not None:
            history.progress_percent = body.progress_percent
    else:
        history = models.ReadingHistory(
            user_id=current_user.id,
            book_id=book_id,
            read_count=1,
            progress_percent=body.progress_percent or 0
        )
        db.add(history)

    db.commit()
    db.refresh(history)
    return {
        "id": history.id,
        "user_id": history.user_id,
        "book_id": history.book_id,
        "read_count": history.read_count,
        "progress_percent": history.progress_percent or 0,
    }


# ─── Reviews ──────────────────────────────────────────────────────────────────

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

    # Construct response manually to inject username
    response = schemas.ReviewResponse.from_orm(review)
    response.username = current_user.username
    return response
