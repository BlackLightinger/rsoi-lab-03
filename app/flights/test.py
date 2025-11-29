from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
import os

# ==============================================
# TEST CONFIGURATION
# ==============================================
os.environ["TESTING"] = "True"

from main import app, get_db, Base, FlightDb, AirportDb, engine

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
def sample_data(db_session):
    # Create test airports
    moscow_airport = AirportDb(
        name="SVO Airport",
        city="Moscow",
        country="Russia"
    )
    spb_airport = AirportDb(
        name="LED Airport",
        city="Saint Petersburg",
        country="Russia"
    )

    db_session.add(moscow_airport)
    db_session.add(spb_airport)
    db_session.commit()

    # Create test flight
    test_flight = FlightDb(
        flight_number="SU100",
        datetime=datetime(2024, 1, 15, 14, 30, 0),
        from_airport_id=moscow_airport.id,
        to_airport_id=spb_airport.id,
        price=7500,
    )

    db_session.add(test_flight)
    db_session.commit()

    return moscow_airport, spb_airport, test_flight


# ==============================================
# TEST CASES: GET /flights
# ==============================================
def test_get_all_flights_list(client, sample_data):
    moscow_airport, spb_airport, flight_data = sample_data

    response = client.get("/flights")

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["totalElements"] == 1
    assert len(response_data["items"]) == 1

    flight_item = response_data["items"][0]
    assert flight_item["flightNumber"] == "SU100"
    assert flight_item["fromAirport"] == "Moscow SVO Airport"
    assert flight_item["toAirport"] == "Saint Petersburg LED Airport"
    assert flight_item["price"] == 7500


def test_get_all_flights_pagination(client, sample_data):
    # Add more flights to test pagination
    moscow_airport, spb_airport, existing_flight = sample_data

    # Add second flight
    second_flight = FlightDb(
        flight_number="SU200",
        datetime=datetime(2024, 1, 16, 10, 0, 0),
        from_airport_id=moscow_airport.id,
        to_airport_id=spb_airport.id,
        price=8000,
    )

    db_session = next(override_get_db())
    db_session.add(second_flight)
    db_session.commit()

    # Test with page size 1
    response = client.get("/flights?page=1&page_size=1")

    assert response.status_code == 200

    response_data = response.json()
    assert response_data["totalElements"] == 2
    assert len(response_data["items"]) == 1
    assert response_data["page"] == 1
    assert response_data["pageSize"] == 1


# ==============================================
# TEST CASES: GET /flights/{flight_number}
# ==============================================
def test_get_flight_by_number_success(client, sample_data):
    moscow_airport, spb_airport, flight_data = sample_data

    response = client.get(f"/flights/SU100")

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["flightNumber"] == "SU100"
    assert response_data["fromAirport"] == "Moscow SVO Airport"
    assert response_data["toAirport"] == "Saint Petersburg LED Airport"
    assert response_data["price"] == 7500


def test_get_flight_by_number_not_found(client, sample_data):
    response = client.get("/flights/NONEXISTENT")

    assert response.status_code == 404


# ==============================================
# TEST CASES: Health Check
# ==============================================
def test_health_check_endpoint(client):
    response = client.get("/manage/health")

    assert response.status_code == 201


# ==============================================
# TEST EXECUTION
# ==============================================
if __name__ == "__main__":
    pytest.main([__file__, "-v"])