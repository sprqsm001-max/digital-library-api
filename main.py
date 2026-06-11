from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
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

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(books.router, prefix="/books", tags=["books"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])

# Health check endpoint
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/debug")
def debug():
    import database
    import os
    # Mask connection details to avoid exposing password
    db_url_masked = None
    if database.DATABASE_URL:
        try:
            db_url_masked = database.DATABASE_URL.split("@")[-1]
        except Exception:
            db_url_masked = "present"
            
    ssh_pw = os.getenv("SSH_PASSWORD", "")
    ssh_pw_masked = f"{ssh_pw[:2]}...{ssh_pw[-2:]} (len: {len(ssh_pw)})" if ssh_pw else None
    
    return {
        "ssh_host": os.getenv("SSH_HOST"),
        "ssh_username": os.getenv("SSH_USERNAME"),
        "ssh_password_set": bool(os.getenv("SSH_PASSWORD")),
        "ssh_password_mask": ssh_pw_masked,
        "database_url_set": bool(os.getenv("DATABASE_URL")),
        "tunnel_active": database.tunnel is not None and getattr(database.tunnel, "is_active", False),
        "tunnel_error": getattr(database, "tunnel_error", None),
        "tunnel_log": getattr(database, "tunnel_log", None),
        "database_url_used": db_url_masked
    }


