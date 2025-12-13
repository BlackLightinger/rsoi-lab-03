from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os
import datetime
import uuid
import sys
import inspect

# ==============================================
# IMPORT CONFIGURATION
# ==============================================
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)

from circuit_breaker import *
from common import *
from services import *

# ==============================================
# SERVICE CONFIGURATION
# ==============================================
FLIGHTS_SERVICE_URL = os.getenv("FLIGHTS_SERVICE_URL")
TICKETS_SERVICE_URL = os.getenv("TICKETS_SERVICE_URL")
PRIVILEGES_SERVICE_URL = os.getenv("PRIVILEGES_SERVICE_URL")

if not FLIGHTS_SERVICE_URL:
    raise RuntimeError("FLIGHTS_SERVICE_URL environment variable is required")
if not TICKETS_SERVICE_URL:
    raise RuntimeError("TICKETS_SERVICE_URL environment variable is required")
if not PRIVILEGES_SERVICE_URL:
    raise RuntimeError("PRIVILEGES_SERVICE_URL environment variable is required")

# Initialize service clients
flight_client = FlightsService(FLIGHTS_SERVICE_URL)
ticket_client = TicketsService(TICKETS_SERVICE_URL)
privilege_client = PrivilegesService(PRIVILEGES_SERVICE_URL)

# ==============================================
# FASTAPI APPLICATION
# ==============================================
app = FastAPI(title="Gateway API", root_path="/api/v1")


# ==============================================
# REQUEST MODELS
# ==============================================
class TicketPurchaseRequest(BaseModel):
    flightNumber: str
    price: int
    paidFromBalance: bool


# ==============================================
# HELPER FUNCTIONS
# ==============================================
def create_error_response(message: str, status_code: int):
    return JSONResponse(
        content=ErrorResponse(message=message).model_dump(),
        status_code=status_code
    )


@app.exception_handler(CircuitOpenException)
async def circuit_open_exception_handler(request, exc):
    return create_error_response(f"{exc.service} unavailable", 503)


def convert_ticket_to_response(ticket_data):
    flight_details = flight_client.get_flight_by_number(ticket_data.flight_number)
    return TicketResponse(
        ticketUid=ticket_data.ticket_uid,
        flightNumber=ticket_data.flight_number,
        fromAirport=flight_details.fromAirport,
        toAirport=flight_details.toAirport,
        date=flight_details.date,
        price=ticket_data.price,
        status=ticket_data.status,
    )


# ==============================================
# API ENDPOINTS
# ==============================================
@app.get("/flights", response_model=PaginationResponse)
def retrieve_flights(page: int = None, size: int = None):
    return flight_client.get_all_flights(page, size)


@app.get("/tickets")
def retrieve_user_tickets(x_user_name: str = Header()) -> List[TicketResponse]:
    user_privilege = privilege_client.get_user_privilege(x_user_name)
    if not user_privilege:
        return create_error_response("User account not found", 404)

    user_tickets = ticket_client.get_user_tickets(x_user_name)
    ticket_responses = []

    for ticket in user_tickets:
        ticket_responses.append(convert_ticket_to_response(ticket))

    return ticket_responses


@app.get("/me")
def get_current_user_profile(x_user_name: str = Header()) -> UserInfoResponse | ErrorResponse:
    try:
        user_privilege = privilege_client.get_user_privilege(x_user_name)
        if not user_privilege:
            return create_error_response("User account not found", 404)
    except CircuitOpenException:
        user_privilege = None

    try:
        user_tickets = ticket_client.get_user_tickets(x_user_name)
        formatted_tickets = []

        for ticket in user_tickets:
            formatted_tickets.append(convert_ticket_to_response(ticket))

    except CircuitOpenException:
        formatted_tickets = []

    if user_privilege is None:
        return UserInfoResponse(tickets=formatted_tickets, privilege="")

    return UserInfoResponse(
        tickets=formatted_tickets,
        privilege=PrivilegeShortInfo(
            balance=user_privilege.balance,
            status=user_privilege.status
        ),
    )


@app.get("/tickets/{ticket_uid}")
def retrieve_ticket_details(
        ticket_uid: uuid.UUID,
        x_user_name: str = Header()
) -> TicketResponse | ErrorResponse:
    ticket_info = ticket_client.get_ticket_by_uid(ticket_uid)
    if not ticket_info:
        return create_error_response("Ticket not found", 404)

    if ticket_info.username != x_user_name:
        return create_error_response("Ticket does not belong to user", 403)

    flight_info = flight_client.get_flight_by_number(ticket_info.flight_number)
    if not flight_info:
        return create_error_response("Flight information not available", 404)

    return TicketResponse(
        ticketUid=ticket_info.ticket_uid,
        flightNumber=ticket_info.flight_number,
        fromAirport=flight_info.fromAirport,
        toAirport=flight_info.toAirport,
        date=flight_info.date,
        price=ticket_info.price,
        status=ticket_info.status,
    )


@app.post("/tickets")
def purchase_ticket(
        purchase_request: TicketPurchaseRequest,
        x_user_name: str = Header()
) -> TicketPurchaseResponse | ValidationErrorResponse:
    flight_info = flight_client.get_flight_by_number(purchase_request.flightNumber)
    if not flight_info:
        return ValidationErrorResponse(
            message="Data validation failed",
            errors=[]
        )

    user_privilege = privilege_client.get_user_privilege(x_user_name)
    if not user_privilege:
        return ValidationErrorResponse(
            message="User does not exist",
            errors=[]
        )

    current_time = datetime.now()
    new_ticket_id = uuid.uuid4()

    cash_payment = flight_info.price
    bonus_payment = 0

    if purchase_request.paidFromBalance:
        bonus_amount = min(user_privilege.balance, flight_info.price)
        bonus_payment = bonus_amount
        cash_payment = flight_info.price - bonus_payment

        if bonus_payment > 0:
            privilege_client.add_privilege_transaction(
                x_user_name,
                AddTransactionRequest(
                    privilege_id=user_privilege.id,
                    ticket_uid=new_ticket_id,
                    datetime=current_time,
                    balance_diff=bonus_payment,
                    operation_type="DEBIT_THE_ACCOUNT",
                ),
            )
    else:
        privilege_client.add_privilege_transaction(
            x_user_name,
            AddTransactionRequest(
                privilege_id=user_privilege.id,
                ticket_uid=new_ticket_id,
                datetime=current_time,
                balance_diff=cash_payment // 10,
                operation_type="FILL_IN_BALANCE",
            ),
        )

    updated_privilege = privilege_client.get_user_privilege(x_user_name)
    ticket_client.create_new_ticket(
        new_ticket_id, x_user_name, flight_info.flightNumber, cash_payment
    )

    return TicketPurchaseResponse(
        ticketUid=new_ticket_id,
        flightNumber=purchase_request.flightNumber,
        fromAirport=flight_info.fromAirport,
        toAirport=flight_info.toAirport,
        date=current_time,
        price=flight_info.price,
        paidByMoney=cash_payment,
        paidByBonuses=bonus_payment,
        status="PAID",
        privilege=PrivilegeShortInfo(
            balance=updated_privilege.balance,
            status=updated_privilege.status
        ),
    )


def cancel_with_retry(
    x_user_name, ticket_uid, max_seconds: int = 10, interval: int = 1
):
    deadline = time.time() + max_seconds
    while time.time() < deadline:
        try:
            if privilege_client.get_user_privelge_transaction(
                x_user_name, ticket_uid
            ):
                privilege_client.rollback_transaction(x_user_name, ticket_uid)
                print("deleted", time.time())
                break
        except CircuitOpenException:
            time.sleep(interval)


@app.delete("/tickets/{ticket_uid}", status_code=204)
def cancel_ticket(ticket_uid: uuid.UUID, x_user_name: str = Header()):
    ticket_info = ticket_client.get_ticket_by_uid(ticket_uid)
    if not ticket_info:
        return create_error_response("Ticket does not exist", 404)

    if ticket_info.username != x_user_name:
        return create_error_response("Ticket does not belong to user", 403)

    if ticket_info.status != "PAID":
        return create_error_response("Ticket cannot be cancelled", 400)

    transaction_record = privilege_client.get_user_privilege_transaction(
        x_user_name, ticket_uid
    )
    if transaction_record:
        privilege_client.revert_transaction(x_user_name, ticket_uid)

    ticket_client.remove_ticket(ticket_uid)


@app.get("/privilege")
def get_user_privilege_info(x_user_name: str = Header()) -> PrivilegeInfoResponse:
    privilege_data = privilege_client.get_user_privilege(x_user_name)
    if not privilege_data:
        return create_error_response("User does not exist", 404)

    history_data = privilege_client.get_user_privilege_history(x_user_name)
    history_entries = []

    for history_item in history_data:
        history_entries.append(
            BalanceHistory(
                date=history_item.datetime,
                ticketUid=history_item.ticket_uid,
                balanceDiff=history_item.balance_diff,
                operationType=history_item.operation_type,
            )
        )

    return PrivilegeInfoResponse(
        balance=privilege_data.balance,
        status=privilege_data.status,
        history=history_entries
    )


@app.get("/manage/health", status_code=201)
def health_check():
    return {"status": "operational"}