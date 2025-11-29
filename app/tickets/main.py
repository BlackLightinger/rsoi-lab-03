import uuid
from fastapi import FastAPI, HTTPException, Depends, Path
from sqlalchemy import create_engine, Column, Integer, String, UUID
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy import Column, Integer, String, StaticPool
from sqlalchemy.orm import declarative_base
import os
import sys
import inspect

# ==============================================
# IMPORT CONFIGURATION
# ==============================================
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)

from common import *

# ==============================================
# DATABASE CONFIGURATION
# ==============================================
if not os.getenv("TESTING"):
    # Environment variables configuration
    DB_USER = os.getenv("POSTGRES_USER", "postgres")
    DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
    DB_NAME = os.getenv("POSTGRES_DB", "postgres")
    DB_HOST = os.getenv("DB_HOST", "postgres")
    DB_PORT = os.getenv("DB_PORT", "5432")

    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    # Database engine setup
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
else:
    # Test environment configuration
    Base = declarative_base()
    SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

# ==============================================
# FASTAPI APPLICATION
# ==============================================
app = FastAPI(title="Tickets API")


# ==============================================
# DATABASE DEPENDENCY
# ==============================================
def get_db():
    database_session = SessionLocal()
    try:
        yield database_session
    finally:
        database_session.close()


# ==============================================
# DATABASE MODELS
# ==============================================
class TicketDb(Base):
    __tablename__ = "ticket"

    id = Column(Integer, primary_key=True)
    ticket_uid = Column(UUID(as_uuid=True), nullable=False)
    username = Column(String(80), nullable=False)
    flight_number = Column(String(20), nullable=False)
    price = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False)


# ==============================================
# API ENDPOINTS
# ==============================================
@app.get("/tickets/user/{username}", response_model=List[Ticket])
def get_user_tickets(username: str, db: Session = Depends(get_db)):
    user_tickets = (
        db.query(TicketDb)
        .filter(TicketDb.username == username)
        .all()
    )
    return user_tickets


@app.get("/tickets/{ticket_uid}", response_model=Ticket)
def get_ticket_details(ticket_uid: uuid.UUID, db: Session = Depends(get_db)):
    ticket_record = (
        db.query(TicketDb)
        .filter(TicketDb.ticket_uid == ticket_uid)
        .first()
    )

    if not ticket_record:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found"
        )

    return ticket_record


@app.post("/tickets", status_code=201)
def create_new_ticket(request: TicketCreateRequest, db: Session = Depends(get_db)):
    # Check for existing ticket with same UUID
    existing_ticket = (
        db.query(TicketDb)
        .filter(TicketDb.ticket_uid == request.ticketUid)
        .first()
    )

    if existing_ticket:
        raise HTTPException(
            status_code=403,
            detail="Ticket with this UUID already exists"
        )

    # Create new ticket
    ticket_entry = TicketDb(
        ticket_uid=request.ticketUid,
        username=request.username,
        flight_number=request.flightNumber,
        price=request.price,
        status="PAID",
    )

    db.add(ticket_entry)
    db.commit()


@app.delete("/tickets/{ticket_uid}", status_code=204)
def remove_ticket(ticket_uid: uuid.UUID, db: Session = Depends(get_db)):
    ticket_record = (
        db.query(TicketDb)
        .filter(TicketDb.ticket_uid == ticket_uid)
        .first()
    )

    if not ticket_record:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found"
        )

    db.delete(ticket_record)
    db.commit()


@app.get("/manage/health", status_code=201)
def health_check():
    return {"status": "operational"}