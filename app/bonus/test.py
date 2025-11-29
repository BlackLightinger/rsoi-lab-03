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

from main import app, get_db, Base, PrivilegeDb, PrivilegeHistoryDb, engine

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
def sample_loyalty_account(db_session):
    loyalty_account = PrivilegeDb(
        username="test_client",
        status="GOLD",
        balance=500
    )
    db_session.add(loyalty_account)
    db_session.commit()

    transaction_record = PrivilegeHistoryDb(
        privilege_id=loyalty_account.id,
        ticket_uid=uuid4(),
        datetime=datetime.now(),
        balance_diff=+200,
        operation_type="FILL_IN_BALANCE",
    )
    db_session.add(transaction_record)
    db_session.commit()

    return loyalty_account, transaction_record


# ==============================================
# TEST CASES: GET /privilege/{username}
# ==============================================
def test_retrieve_loyalty_account_success(client, sample_loyalty_account):
    account_data, _ = sample_loyalty_account

    response = client.get(f"/privilege/{account_data.username}")

    assert response.status_code == 200

    response_data = response.json()
    assert response_data["username"] == account_data.username
    assert response_data["status"] == "GOLD"
    assert response_data["balance"] == 500


def test_retrieve_loyalty_account_not_exists(client):
    response = client.get("/privilege/nonexistent_client")

    assert response.status_code == 404


# ==============================================
# TEST CASES: GET /privilege/{username}/history
# ==============================================
def test_retrieve_account_transaction_history(client, sample_loyalty_account):
    account_data, transaction_data = sample_loyalty_account

    response = client.get(f"/privilege/{account_data.username}/history")

    assert response.status_code == 200

    response_data = response.json()
    assert isinstance(response_data, list)
    assert len(response_data) == 1
    assert response_data[0]["operation_type"] == "FILL_IN_BALANCE"
    assert response_data[0]["balance_diff"] == 200


# ==============================================
# TEST CASES: GET /privilege/{username}/history/{ticket_uid}
# ==============================================
def test_retrieve_specific_transaction(client, sample_loyalty_account):
    account_data, transaction_data = sample_loyalty_account

    response = client.get(
        f"/privilege/{account_data.username}/history/{transaction_data.ticket_uid}"
    )

    assert response.status_code == 200

    response_data = response.json()
    assert response_data["ticket_uid"] == str(transaction_data.ticket_uid)
    assert response_data["operation_type"] == "FILL_IN_BALANCE"


def test_retrieve_nonexistent_transaction(client, sample_loyalty_account):
    account_data, _ = sample_loyalty_account
    response = client.get(f"/privilege/{account_data.username}/history/{uuid4()}")

    assert response.status_code == 404


# ==============================================
# TEST CASES: POST /privilege/{username}/history
# ==============================================
def test_create_new_transaction(client, sample_loyalty_account):
    account_data, _ = sample_loyalty_account
    new_ticket_id = str(uuid4())

    request_payload = {
        "ticket_uid": new_ticket_id,
        "balance_diff": 150,
        "operation_type": "DEBIT_THE_ACCOUNT",
        "privilege_id": account_data.id,
        "datetime": datetime.now().isoformat(),
    }

    response = client.post(
        f"/privilege/{account_data.username}/history",
        json=request_payload
    )

    assert response.status_code == 201

    # Verify account balance was updated
    account_check = client.get(f"/privilege/{account_data.username}")

    assert account_check.status_code == 200

    updated_account = account_check.json()
    assert updated_account["balance"] == 350  # 500 - 150


def test_create_transaction_invalid_operation(client, sample_loyalty_account):
    account_data, _ = sample_loyalty_account

    request_payload = {
        "ticket_uid": str(uuid4()),
        "balance_diff": 100,
        "operation_type": "INVALID_OPERATION",  # Invalid operation type
    }

    response = client.post(
        f"/privilege/{account_data.username}/history",
        json=request_payload
    )

    assert response.status_code in [400, 422]  # Bad Request or Validation Error


# ==============================================
# TEST CASES: DELETE /privilege/{username}/history/{ticket_uid}
# ==============================================
def test_remove_transaction(client, sample_loyalty_account):
    account_data, transaction_data = sample_loyalty_account

    response = client.delete(
        f"/privilege/{account_data.username}/history/{transaction_data.ticket_uid}"
    )

    assert response.status_code == 204

    # Verify transaction was removed
    check_response = client.get(
        f"/privilege/{account_data.username}/history/{transaction_data.ticket_uid}"
    )

    assert check_response.status_code == 404


def test_remove_nonexistent_transaction(client, sample_loyalty_account):
    account_data, _ = sample_loyalty_account

    response = client.delete(f"/privilege/{account_data.username}/history/{uuid4()}")

    assert response.status_code == 404


# ==============================================
# TEST EXECUTION
# ==============================================
if __name__ == "__main__":
    pytest.main([__file__, "-v"])