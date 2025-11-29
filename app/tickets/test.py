from datetime import datetime
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
import os

# ==============================================
# TEST CONFIGURATION
# ==============================================
os.environ["TESTING"] = "True"

from main import app, get_db, Base, TicketDb, engine

# ==============================================
# DATABASE SETUP FOR TESTING
# ==============================================
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db_session = TestingSessionLocal()
        yield db_session
    finally:
        db_session.close()


app.dependency_overrides[get_db] = override_get_db


# ==============================================
# TEST FIXTURES
# ==============================================
@pytest.fixture(scope="function")
def db_session():
    """
    Creates a fresh database session for test execution
    """
    Base.metadata.create_all(bind=engine)

    test_session = TestingSessionLocal()
    try:
        yield test_session
    finally:
        test_session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    Base.metadata.create_all(bind=engine)
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_ticket(db_session):
    ticket_record = TicketDb(
        ticket_uid=uuid4(),
        username="test_user",
        flight_number="FL123",
        price=2500,
        status="PAID",
    )
    db_session.add(ticket_record)
    db_session.commit()

    return ticket_record


# ==============================================
# TEST CASES: GET /tickets/user/{username}
# ==============================================
def test_get_tickets_for_nonexistent_user(client):
    response = client.get("/tickets/user/nonexistent_user")

    assert response.status_code == 200
    assert len(response.json()) == 0


def test_get_tickets_for_existing_user(client, sample_ticket):
    response = client.get(f"/tickets/user/{sample_ticket.username}")

    assert response.status_code == 200

    response_data = response.json()
    assert len(response_data) == 1
    assert response_data[0]["username"] == sample_ticket.username
    assert response_data[0]["flight_number"] == sample_ticket.flight_number
    assert response_data[0]["price"] == 2500


# ==============================================
# TEST CASES: GET /tickets/{ticket_uid}
# ==============================================
def test_get_nonexistent_ticket(client):
    response = client.get(f"/tickets/{uuid4()}")

    assert response.status_code == 404


def test_get_existing_ticket(client, sample_ticket):
    response = client.get(f"/tickets/{sample_ticket.ticket_uid}")

    assert response.status_code == 200

    response_data = response.json()
    assert response_data["username"] == sample_ticket.username
    assert response_data["flight_number"] == sample_ticket.flight_number
    assert response_data["status"] == "PAID"
    assert response_data["price"] == 2500


# ==============================================
# TEST CASES: POST /tickets
# ==============================================
def test_create_new_ticket_success(client):
    new_ticket_id = uuid4()

    response = client.post(
        "/tickets/",
        json={
            "ticketUid": str(new_ticket_id),
            "username": "new_user",
            "flightNumber": "AB456",
            "price": 3000,
        },
    )

    assert response.status_code == 201

    # Verify ticket was created
    verification_response = client.get(f"/tickets/{new_ticket_id}")

    assert verification_response.status_code == 200

    ticket_data = verification_response.json()
    assert ticket_data["username"] == "new_user"
    assert ticket_data["flight_number"] == "AB456"
    assert ticket_data["price"] == 3000
    assert ticket_data["status"] == "PAID"


def test_create_duplicate_ticket(client):
    duplicate_uuid = uuid4()

    # First creation should succeed
    first_response = client.post(
        "/tickets/",
        json={
            "ticketUid": str(duplicate_uuid),
            "username": "user1",
            "flightNumber": "FL100",
            "price": 1500,
        },
    )
    assert first_response.status_code == 201

    # Second creation with same UUID should fail
    second_response = client.post(
        "/tickets/",
        json={
            "ticketUid": str(duplicate_uuid),
            "username": "user2",
            "flightNumber": "FL200",
            "price": 2000,
        },
    )
    assert second_response.status_code == 403


# ==============================================
# TEST CASES: DELETE /tickets/{ticket_uid}
# ==============================================
def test_delete_existing_ticket(client, sample_ticket):
    # Delete the ticket
    delete_response = client.delete(f"/tickets/{sample_ticket.ticket_uid}")

    assert delete_response.status_code == 204

    # Verify ticket is gone
    get_response = client.get(f"/tickets/{sample_ticket.ticket_uid}")

    assert get_response.status_code == 404


def test_delete_nonexistent_ticket(client):
    response = client.delete(f"/tickets/{uuid4()}")

    assert response.status_code == 404


# ==============================================
# TEST EXECUTION
# ==============================================
if __name__ == "__main__":
    pytest.main([__file__, "-v"])