from common import *
import requests
from circuit_breaker import CircuitBreaker, CircuitOpenException
from functools import wraps


def wrap_cb(service):

    def wrap_cb(fn):
        cb = CircuitBreaker(service, failure_threshold=1, recovery_timeout=1)

        @wraps(fn)
        def wrapper(*args, **kwargs):
            return cb.call(fn, *args, **kwargs)

        return wrapper

    return wrap_cb



# ==============================================
# FLIGHTS SERVICE CLIENT
# ==============================================

class FlightsService:
    NAME = "Flights Service"

    def __init__(self, base_url):
        self.base_url = base_url

    def health_check(self):
        response = requests.get(f"{self.base_url}/manage/health")
        response.raise_for_status()

    @wrap_cb(NAME)
    def get_all_flights(self, page: int = None, size: int = None):
        query_params = {"page": page, "size": size}
        response = requests.get(f"{self.base_url}/flights", params=query_params)
        response.raise_for_status()
        return PaginationResponse.model_validate(response.json())

    @wrap_cb(NAME)
    def get_flight_by_number(self, flight_number: str) -> FlightResponse:
        response = requests.get(f"{self.base_url}/flights/{flight_number}")
        response.raise_for_status()
        return FlightResponse.model_validate(response.json())

    def get_flight_by_number_or_default(self, flight_number: str) -> FlightResponse:
        try:
            return self.get_flight_by_number(flight_number)
        except CircuitOpenException:
            return FlightResponse(
                flightNumber="XXX",
                fromAirport="XXX",
                toAirport="XXX",
                date=datetime.fromordinal(1),
                price=0,
            )


# ==============================================
# TICKETS SERVICE CLIENT
# ==============================================

class TicketsService:
    NAME = "Ticket Service"

    def __init__(self, base_url):
        self.base_url = base_url

    def health_check(self):
        response = requests.get(f"{self.base_url}/manage/health")
        response.raise_for_status()

    @wrap_cb(NAME)
    def get_user_tickets(self, username: str) -> list[Ticket]:
        response = requests.get(f"{self.base_url}/tickets/user/{username}")
        response.raise_for_status()
        return [Ticket.model_validate(item) for item in response.json()]

    @wrap_cb(NAME)
    def get_ticket_by_uid(self, ticket_uid: uuid.UUID) -> Ticket | None:
        response = requests.get(f"{self.base_url}/tickets/{ticket_uid}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return Ticket.model_validate(response.json())

    def remove_ticket(self, ticket_uid: uuid.UUID) -> None:
        response = requests.delete(f"{self.base_url}/tickets/{ticket_uid}")
        response.raise_for_status()

    def create_new_ticket(self, ticket_uid: uuid.UUID, username: str, flight_number: str, price: int):
        ticket_data = TicketCreateRequest(
            ticketUid=ticket_uid,
            username=username,
            flightNumber=flight_number,
            price=price,
        )
        response = requests.post(
            f"{self.base_url}/tickets",
            json=ticket_data.model_dump(mode="json")
        )
        response.raise_for_status()


# ==============================================
# PRIVILEGES SERVICE CLIENT
# ==============================================

class PrivilegesService:
    NAME = "Bonus Service"

    def __init__(self, base_url):
        self.base_url = base_url

    def health_check(self):
        response = requests.get(f"{self.base_url}/manage/health")
        response.raise_for_status()

    @wrap_cb(NAME)
    def get_user_privilege(self, username: str) -> Privilege | None:
        response = requests.get(f"{self.base_url}/privilege/{username}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return Privilege.model_validate(response.json())

    @wrap_cb(NAME)
    def get_user_privilege_history(self, username: str) -> list[PrivilegeHistory]:
        response = requests.get(f"{self.base_url}/privilege/{username}/history")
        response.raise_for_status()
        return [PrivilegeHistory.model_validate(item) for item in response.json()]

    @wrap_cb(NAME)
    def get_user_privilege_transaction(self, username: str, ticket_uid: uuid.UUID) -> PrivilegeHistory | None:
        response = requests.get(f"{self.base_url}/privilege/{username}/history/{ticket_uid}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return PrivilegeHistory.model_validate(response.json())

    def add_privilege_transaction(self, username: str, transaction_data: AddTransactionRequest):
        response = requests.post(
            f"{self.base_url}/privilege/{username}/history",
            json=transaction_data.model_dump(mode="json")
        )
        response.raise_for_status()

    def revert_transaction(self, username: str, ticket_uid: uuid.UUID):
        response = requests.delete(
            f"{self.base_url}/privilege/{username}/history/{ticket_uid}"
        )
        response.raise_for_status()