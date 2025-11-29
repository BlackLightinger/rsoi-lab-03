import inspect
import sys
from fastapi import FastAPI, HTTPException, Depends, Query
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, StaticPool
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import os


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
app = FastAPI(title="Flight API")


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
class AirportDb(Base):
    __tablename__ = "airport"

    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    city = Column(String(255))
    country = Column(String(255))

    # Airport relationships
    departures = relationship(
        "FlightDb",
        back_populates="from_airport",
        foreign_keys="FlightDb.from_airport_id",
    )
    arrivals = relationship(
        "FlightDb",
        back_populates="to_airport",
        foreign_keys="FlightDb.to_airport_id"
    )


class FlightDb(Base):
    __tablename__ = "flight"

    id = Column(Integer, primary_key=True)
    flight_number = Column(String(20), nullable=False)
    datetime = Column(TIMESTAMP(timezone=True))
    from_airport_id = Column(Integer, ForeignKey("airport.id"))
    to_airport_id = Column(Integer, ForeignKey("airport.id"))
    price = Column(Integer, nullable=False)

    # Flight relationships
    from_airport = relationship(
        "AirportDb",
        foreign_keys=[from_airport_id],
        back_populates="departures"
    )
    to_airport = relationship(
        "AirportDb",
        foreign_keys=[to_airport_id],
        back_populates="arrivals"
    )


# ==============================================
# HELPER FUNCTIONS
# ==============================================
def flight_to_response(flight_record: FlightDb) -> FlightResponse:
    departure_airport = f"{flight_record.from_airport.city} {flight_record.from_airport.name}"
    arrival_airport = f"{flight_record.to_airport.city} {flight_record.to_airport.name}"

    return FlightResponse(
        flightNumber=flight_record.flight_number,
        fromAirport=departure_airport,
        toAirport=arrival_airport,
        date=flight_record.datetime.isoformat(),
        price=flight_record.price,
    )


# ==============================================
# API ENDPOINTS
# ==============================================
@app.get("/flights", response_model=PaginationResponse)
def get_all_flights(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(
        10, ge=1, le=100, description="Items per page"
    ),
    db: Session = Depends(get_db),
):
    # Calculate pagination offset
    offset_value = (page - 1) * page_size

    # Get total count and paginated results
    total_count = db.query(FlightDb).count()
    flight_records = db.query(FlightDb).offset(offset_value).limit(page_size).all()

    # Convert to response format
    response_items = [flight_to_response(flight) for flight in flight_records]

    return PaginationResponse(
        page=page,
        pageSize=page_size,
        totalElements=total_count,
        items=response_items,
    )


@app.get("/flights/{flight_number}", response_model=FlightResponse)
def get_flight_by_number(
    flight_number: str,
    db: Session = Depends(get_db)
):
    flight_record = (
        db.query(FlightDb)
        .filter(FlightDb.flight_number == flight_number)
        .first()
    )

    if not flight_record:
        raise HTTPException(
            status_code=404,
            detail="Flight not found"
        )

    return flight_to_response(flight_record)


@app.get("/manage/health", status_code=201)
def health_check():
    return {"status": "operational"}