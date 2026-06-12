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

@asynccontextmanager
async def lifespan(app: FastAPI):
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
        "db_error": db_error
    }





