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


