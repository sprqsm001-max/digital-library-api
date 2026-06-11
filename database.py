import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SSH_HOST = os.getenv("SSH_HOST")
SSH_PORT = int(os.getenv("SSH_PORT", "22"))
SSH_USERNAME = os.getenv("SSH_USERNAME")
SSH_PASSWORD = os.getenv("SSH_PASSWORD")

tunnel = None
tunnel_error = None

if SSH_HOST and SSH_USERNAME:
    try:
        from sshtunnel import SSHTunnelForwarder
        tunnel = SSHTunnelForwarder(
            (SSH_HOST, SSH_PORT),
            ssh_username=SSH_USERNAME,
            ssh_password=SSH_PASSWORD,
            remote_bind_address=('127.0.0.1', 5432),
            local_bind_address=('127.0.0.1', 5433)
        )
        tunnel.start()
        print("SSH Tunnel started successfully.")
        
        # Rewrite DATABASE_URL to use the local endpoint of the tunnel
        if DATABASE_URL:
            for schema in ["postgresql://", "postgres://"]:
                if DATABASE_URL.startswith(schema):
                    rest = DATABASE_URL[len(schema):]
                    creds, path = rest.split("@", 1)
                    host_port, dbname = path.split("/", 1)
                    DATABASE_URL = f"{schema}{creds}@127.0.0.1:5433/{dbname}"
                    break
    except Exception as e:
        tunnel_error = str(e)
        print(f"Failed to start SSH Tunnel: {e}")

if not DATABASE_URL:
    # Fallback to an empty string during imports/testing if needed
    DATABASE_URL = "postgresql://localhost/dummy"

# Render sometimes uses postgres://, SQLAlchemy expects postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get db session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

