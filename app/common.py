import uuid
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
from enum import Enum


# ==============================================
# DATABASE ENTITY MODELS
# ==============================================

class Ticket(BaseModel):
    id: int
    ticket_uid: uuid.UUID
    username: str
    flight_number: str
    price: int
    status: str

    model_config = ConfigDict(from_attributes=True)


class Flight(BaseModel):
    id: int
    flight_number: str
    datetime: datetime
    from_airport_id: int
    to_airport_id: int
    price: int

    model_config = ConfigDict(from_attributes=True)


class Airport(BaseModel):
    id: int
    name: str
    city: str
    country: str

    model_config = ConfigDict(from_attributes=True)


class Privilege(BaseModel):
    id: int
    username: str
    status: str
    balance: int

    model_config = ConfigDict(from_attributes=True)


class PrivilegeHistory(BaseModel):
    id: int
    privilege_id: int
    ticket_uid: uuid.UUID
    datetime: datetime
    balance_diff: int
    operation_type: str

    model_config = ConfigDict(from_attributes=True)


# ==============================================
# ENUMERATION TYPES
# ==============================================

class TicketStatus(str, Enum):
    PAID = "PAID"
    CANCELED = "CANCELED"


class PrivilegeStatus(str, Enum):
    BRONZE = "BRONZE"
    SILVER = "SILVER"
    GOLD = "GOLD"


class OperationType(str, Enum):
    FILL_IN_BALANCE = "FILL_IN_BALANCE"
    DEBIT_THE_ACCOUNT = "DEBIT_THE_ACCOUNT"


# ==============================================
# FLIGHT RELATED MODELS
# ==============================================

class FlightResponse(BaseModel):
    flightNumber: str
    fromAirport: str
    toAirport: str
    date: datetime
    price: int

    model_config = ConfigDict(from_attributes=True)


class PaginationResponse(BaseModel):
    page: int
    pageSize: int
    totalElements: int
    items: List[FlightResponse]

    model_config = ConfigDict(from_attributes=True)


# ==============================================
# TICKET RELATED MODELS
# ==============================================

class TicketResponse(BaseModel):
    ticketUid: uuid.UUID
    flightNumber: str
    fromAirport: str
    toAirport: str
    date: datetime
    price: int
    status: TicketStatus

    model_config = ConfigDict(from_attributes=True)


class TicketPurchaseRequest(BaseModel):
    flightNumber: str
    price: int
    paidFromBalance: bool


class TicketPurchaseResponse(BaseModel):
    ticketUid: uuid.UUID
    flightNumber: str
    fromAirport: str
    toAirport: str
    date: datetime
    price: int
    paidByMoney: int
    paidByBonuses: int
    status: TicketStatus
    privilege: "PrivilegeShortInfo"


class TicketCreateRequest(BaseModel):
    ticketUid: uuid.UUID
    username: str
    flightNumber: str
    price: int


# ==============================================
# PRIVILEGE AND LOYALTY MODELS
# ==============================================

class PrivilegeShortInfo(BaseModel):
    balance: int
    status: PrivilegeStatus

    model_config = ConfigDict(from_attributes=True)


class BalanceHistory(BaseModel):
    date: datetime
    ticketUid: uuid.UUID
    balanceDiff: int
    operationType: OperationType

    model_config = ConfigDict(from_attributes=True)


class PrivilegeInfoResponse(BaseModel):
    balance: int
    status: PrivilegeStatus
    history: List[BalanceHistory]


class AddTransactionRequest(BaseModel):
    privilege_id: int
    ticket_uid: uuid.UUID
    datetime: datetime
    balance_diff: int
    operation_type: str


# ==============================================
# USER PROFILE MODELS
# ==============================================

class UserInfoResponse(BaseModel):
    tickets: List[TicketResponse]
    privilege: PrivilegeShortInfo


# ==============================================
# ERROR HANDLING MODELS
# ==============================================

class ErrorDescription(BaseModel):
    field: str
    error: str


class ErrorResponse(BaseModel):
    message: str


class ValidationErrorResponse(BaseModel):
    message: str
    errors: List[ErrorDescription]