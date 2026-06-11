from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas
from utils.auth import get_password_hash, verify_password, create_access_token, get_current_active_user
from pydantic import BaseModel

router = APIRouter()

# Schema for JSON logins
class LoginRequest(BaseModel):
    username: str  # Can be username or email
    password: str

@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    # Check if username or email already exists
    existing_user = db.query(models.User).filter(
        (models.User.email == user_in.email) | (models.User.username == user_in.username)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )
    
    # First user is admin (helps bootstrapping)
    user_count = db.query(models.User).count()
    role = "admin" if user_count == 0 else "reader"
    
    hashed_password = get_password_hash(user_in.password)
    db_user = models.User(
        email=user_in.email,
        username=user_in.username,
        password_hash=hashed_password,
        role=role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.post("/login", response_model=schemas.Token)
def login(login_in: LoginRequest, db: Session = Depends(get_db)):
    # Authenticate by username or email
    user = db.query(models.User).filter(
        (models.User.email == login_in.username) | (models.User.username == login_in.username)
    ).first()
    
    if not user or not verify_password(login_in.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect username/email or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is deactivated"
        )
    
    access_token = create_access_token(
        data={"user_id": user.id, "role": user.role}
    )
    user_data = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None
    }
    return {"access_token": access_token, "token_type": "bearer", "user": user_data}

@router.get("/me", response_model=schemas.UserResponse)
def get_me(current_user: models.User = Depends(get_current_active_user)):
    return current_user

@router.post("/logout")
def logout():
    # Since we are using stateless JWT tokens, client-side handles deletion
    # We just return success message
    return {"detail": "Successfully logged out"}
