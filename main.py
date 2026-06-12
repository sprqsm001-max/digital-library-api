from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import sys
import traceback
from dotenv import load_dotenv

# Add current directory to path to ensure proper package imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from routers import auth, books, users, admin

from contextlib import asynccontextmanager

load_dotenv()

last_traceback = None

def run_auto_migrations():
    """Apply incremental schema changes that models can't handle via create_all."""
    try:
        from database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        migrations = [
            # Add progress_percent to reading_history if it doesn't exist
            "ALTER TABLE reading_history ADD COLUMN IF NOT EXISTS progress_percent INTEGER DEFAULT 0;",
            # Create epub_media table if it doesn't exist
            """
            CREATE TABLE IF NOT EXISTS epub_media (
                id SERIAL PRIMARY KEY,
                book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,
                file_path VARCHAR(500) NOT NULL,
                content_type VARCHAR(100) NOT NULL,
                file_bytes BYTEA NOT NULL
            );
            """,
            # Create index on epub_media if it doesn't exist
            "CREATE INDEX IF NOT EXISTS idx_epub_media_book_path ON epub_media (book_id, file_path);"
        ]
        for sql in migrations:
            try:
                db.execute(text(sql))
                db.commit()
                print(f"[migration] Applied: {sql[:60].strip()}...")
            except Exception as e:
                db.rollback()
                print(f"[migration] Skipped (may already exist): {e}")
        db.close()
        print("[migration] Auto-migrations complete.")
    except Exception as e:
        print(f"[migration] Auto-migration failed: {e}")

def run_epub_image_migrations():
    """Extract and save images for existing EPUB books in the database if not already done."""
    try:
        from database import SessionLocal
        import models
        from utils.epub_parser import parse_epub_metadata
        import os
        import mimetypes
        
        db = SessionLocal()
        books = db.query(models.Book).filter(models.Book.file_type == "epub").all()
        print(f"[migration] Checking {len(books)} EPUB books for image migrations.")
        
        static_dir = os.path.dirname(os.path.abspath(__file__))
        
        for book in books:
            # Check if this book already has media
            media_count = db.query(models.EPUBMedia).filter(models.EPUBMedia.book_id == book.id).count()
            if media_count > 0:
                print(f"[migration] Book ID {book.id} ('{book.title}') already has {media_count} images extracted.")
                continue
                
            # If not, let's try to extract from the EPUB file
            if not book.file_url:
                continue
            filename = book.file_url.split("/")[-1]
            epub_path = os.path.join(static_dir, "static", "uploads", "books", filename)
            
            if not os.path.exists(epub_path):
                print(f"[migration] EPUB file not found on server for Book ID {book.id}: {epub_path}")
                continue
                
            print(f"[migration] Extracting images for Book ID {book.id} ('{book.title}')...")
            with open(epub_path, "rb") as f:
                epub_bytes = f.read()
                
            epub_data = parse_epub_metadata(epub_bytes)
            if not epub_data:
                continue
                
            extracted_images = epub_data.get("extracted_images", {})
            if extracted_images:
                for relative_path, img_bytes in extracted_images.items():
                    content_type, _ = mimetypes.guess_type(relative_path)
                    if not content_type:
                        content_type = "image/jpeg"
                    
                    db_media = models.EPUBMedia(
                        book_id=book.id,
                        file_path=relative_path,
                        content_type=content_type,
                        file_bytes=img_bytes
                    )
                    db.add(db_media)
                
                # Replace the relative path references in content_text to point to the media serving endpoint
                content_text = epub_data["content_text"].replace(
                    "__EPUB_MEDIA__/",
                    f"/books/{book.id}/media/"
                )
                book.content_text = content_text
                db.commit()
                print(f"[migration] Successfully migrated {len(extracted_images)} images for Book ID {book.id}!")
        db.close()
    except Exception as e:
        print(f"[migration] EPUB image migration failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run schema migrations on startup
    run_auto_migrations()
    # Run EPUB image migrations on startup
    run_epub_image_migrations()
    yield
    try:
        from database import tunnel
        if tunnel:
            print("Stopping SSH Tunnel...")
            tunnel.stop()
            print("SSH Tunnel stopped.")
    except Exception as e:
        print(f"Error closing SSH tunnel: {e}")

app = FastAPI(
    title="Digital Library API",
    description="Backend for the African Digital Library",
    version="1.0.0",
    lifespan=lifespan
)

# CORS config — allow live frontend + local dev
FRONTEND_URL = os.getenv("FRONTEND_URL", "")

origins = [
    "https://www.oldafricanbooks.com",
    "https://oldafricanbooks.com",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

if FRONTEND_URL and FRONTEND_URL not in origins:
    origins.append(FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True if "*" not in origins else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler — ensures 500 errors return JSON with CORS headers
# Without this, unhandled DB errors return plain-text 500s that browsers block as CORS errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    global last_traceback
    last_traceback = traceback.format_exc()
    print(f"Unhandled error on {request.method} {request.url.path}: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Database may be temporarily unavailable."}
    )

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(books.router, prefix="/books", tags=["books"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])

# Mount static files directory
from fastapi.staticfiles import StaticFiles
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(os.path.join(STATIC_DIR, "uploads", "books"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "uploads", "covers"), exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# Health check endpoint
@app.get("/health")
def health():
    from database import tunnel, tunnel_error, SessionLocal
    db_error = None
    try:
        db = SessionLocal()
        # Test basic query
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db.close()
    except Exception as e:
        db_error = str(e)
        
    return {
        "status": "ok" if not db_error else "db_error",
        "ssh_tunnel": "connected" if tunnel and tunnel.is_active else "disconnected",
        "tunnel_error": tunnel_error,
        "db_error": db_error,
        "last_error": last_traceback,
        "env": {k: (v[:15] + "..." if len(v) > 15 else "...") if any(x in k.lower() for x in ["url", "pass", "secret", "key", "token"]) else v for k, v in os.environ.items()}
    }






