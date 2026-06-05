from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
from dotenv import load_dotenv

# Add current directory to path to ensure proper package imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from routers import auth, books, users, admin

load_dotenv()

app = FastAPI(
    title="Digital Library API",
    description="Backend for the African Digital Library",
    version="1.0.0"
)

# CORS config
FRONTEND_URL = os.getenv("FRONTEND_URL", "*")
origins = [
    "https://yourdomain.com",
    "https://www.yourdomain.com"
]

if FRONTEND_URL and FRONTEND_URL != "*":
    origins.append(FRONTEND_URL)
    # Include common local development ports
    origins.extend([
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ])
else:
    origins = ["*"]

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
