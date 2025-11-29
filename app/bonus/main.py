import inspect
import sys
import uuid
from fastapi import FastAPI, HTTPException, Depends, Path
from sqlalchemy import (
    TIMESTAMP,
    CheckConstraint,
    ForeignKey,
    StaticPool,
    create_engine,
    Column,
    Integer,
    String,
    UUID,
)
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base, relationship
import os

# ==============================================
# IMPORT CONFIGURATION
# ==============================================
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)

from common import *

# ==============================================
# DATABASE SETUP
# ==============================================
if not os.getenv("TESTING"):
    DB_USER = os.getenv("POSTGRES_USER", "postgres")
    DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
    DB_NAME = os.getenv("POSTGRES_DB", "postgres")
    DB_HOST = os.getenv("DB_HOST", "postgres")
    DB_PORT = os.getenv("DB_PORT", "5432")

    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
else:
    Base = declarative_base()
    SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


# ==============================================
# DATABASE MODELS
# ==============================================
class PrivilegeDb(Base):
    __tablename__ = "privilege"

    id = Column(Integer, primary_key=True)
    username = Column(String(80), nullable=False, unique=True)
    status = Column(String(80), nullable=False, default="BRONZE")
    balance = Column(Integer, nullable=True, default=0)

    __table_args__ = (
        CheckConstraint(
            "status IN ('BRONZE', 'SILVER', 'GOLD')",
            name="privilege_status_check"
        ),
    )

    history = relationship(
        "PrivilegeHistoryDb",
        back_populates="privilege",
        cascade="all, delete"
    )


class PrivilegeHistoryDb(Base):
    __tablename__ = "privilege_history"

    id = Column(Integer, primary_key=True)
    privilege_id = Column(Integer, ForeignKey("privilege.id"))
    ticket_uid = Column(UUID(as_uuid=True), nullable=False)
    datetime = Column(TIMESTAMP, nullable=False)
    balance_diff = Column(Integer, nullable=False)
    operation_type = Column(String(20), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "operation_type IN ('FILL_IN_BALANCE', 'DEBIT_THE_ACCOUNT')",
            name="privilege_operation_type_check",
        ),
    )

    privilege = relationship("PrivilegeDb", back_populates="history")


# ==============================================
# FASTAPI APPLICATION
# ==============================================
app = FastAPI(title="Privilege Service", version="1.0")


# ==============================================
# DEPENDENCIES
# ==============================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==============================================
# API ENDPOINTS
# ==============================================
@app.get("/privilege/{username}", response_model=Privilege)
def get_privilege_by_username(
        username: str,
        db: Session = Depends(get_db)
):
    privilege = (
        db.query(PrivilegeDb)
        .filter(PrivilegeDb.username == username)
        .first()
    )

    if not privilege:
        raise HTTPException(
            status_code=404,
            detail="Privilege not found for this user"
        )

    return privilege


@app.get("/privilege/{username}/history", response_model=List[PrivilegeHistory])
def get_privilege_history_by_username(
        username: str,
        db: Session = Depends(get_db)
):
    privilege = (
        db.query(PrivilegeDb)
        .filter(PrivilegeDb.username == username)
        .first()
    )

    if not privilege:
        raise HTTPException(
            status_code=404,
            detail="Privilege not found for this user"
        )

    history = (
        db.query(PrivilegeHistoryDb)
        .filter(PrivilegeHistoryDb.privilege_id == privilege.id)
        .order_by(PrivilegeHistoryDb.datetime.desc())
        .all()
    )

    return history


@app.get(
    "/privilege/{username}/history/{ticket_uid}",
    response_model=PrivilegeHistory,
)
def get_specific_history_entry(
        username: str,
        ticket_uid: uuid.UUID = Path(..., description="UUID билета"),
        db: Session = Depends(get_db),
):
    privilege = (
        db.query(PrivilegeDb)
        .filter(PrivilegeDb.username == username)
        .first()
    )

    if not privilege:
        raise HTTPException(
            status_code=404,
            detail="Privilege not found for this user"
        )

    history_entry = (
        db.query(PrivilegeHistoryDb)
        .filter(
            PrivilegeHistoryDb.privilege_id == privilege.id,
            PrivilegeHistoryDb.ticket_uid == ticket_uid,
        )
        .first()
    )

    if not history_entry:
        raise HTTPException(
            status_code=404,
            detail="History entry not found"
        )

    return history_entry


@app.post("/privilege/{username}/history", status_code=201)
def add_transaction(
        username: str,
        data: AddTransactionRequest,
        db: Session = Depends(get_db)
):
    priv = (
        db.query(PrivilegeDb)
        .filter(PrivilegeDb.username == username)
        .first()
    )

    if not priv:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    if data.operation_type == "FILL_IN_BALANCE":
        priv.balance += data.balance_diff
    else:
        if priv.balance < data.balance_diff:
            raise HTTPException(
                status_code=409,
                detail="Can't decrease balance"
            )
        priv.balance -= data.balance_diff

    hist = PrivilegeHistoryDb(
        privilege_id=priv.id,
        ticket_uid=data.ticket_uid,
        datetime=data.datetime,
        balance_diff=data.balance_diff,
        operation_type=data.operation_type,
    )

    db.add(hist)
    db.commit()
    db.refresh(priv)


@app.delete("/privilege/{username}/history/{ticket_uid}", status_code=204)
def rollback_transaction(
        username: str,
        ticket_uid: uuid.UUID,
        db: Session = Depends(get_db)
):
    priv = (
        db.query(PrivilegeDb)
        .filter(PrivilegeDb.username == username)
        .first()
    )

    if not priv:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    transaction = (
        db.query(PrivilegeHistoryDb)
        .filter(
            PrivilegeHistoryDb.privilege_id == priv.id,
            PrivilegeHistoryDb.ticket_uid == ticket_uid,
        )
        .first()
    )

    if not transaction:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found"
        )

    cur_balance = priv.balance

    if transaction.operation_type == "FILL_IN_BALANCE":
        new_balance = max(cur_balance - transaction.balance_diff, 0)
    else:
        new_balance = cur_balance + transaction.balance_diff

    priv.balance = new_balance
    db.delete(transaction)
    db.commit()
    db.refresh(priv)


@app.get("/manage/health", status_code=201)
def health():
    return {"status": "healthy"}