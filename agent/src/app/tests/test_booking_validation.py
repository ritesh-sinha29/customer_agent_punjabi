import pytest
from unittest.mock import patch
from src.app.tools.booking_tools import create_booking, get_booking_updates

@patch("src.app.tools.booking_tools.db_service.execute_insert")
def test_create_booking_valid(mock_insert):
    mock_insert.return_value = {
        "id": "b-test1234",
        "product_name": "Horsa-550X-Turbo",
        "qty": 5,
        "user_id": "u-test",
        "status": "requested",
    }
    
    res = create_booking.invoke({"user_id": "u-test", "items": [{"product_name": "Horsa-550X-Turbo", "qty": 5}]})
    
    mock_insert.assert_called_once()
    args, kwargs = mock_insert.call_args
    params = args[1]
    assert params[1] == "Horsa-550X-Turbo"
    assert params[2] == 5
    assert params[3] == "u-test"
    assert len(res) == 1
    assert res[0]["product_name"] == "Horsa-550X-Turbo"

@patch("src.app.tools.booking_tools.db_service.execute_query")
def test_get_booking_updates(mock_query):
    mock_query.return_value = [
        {
            "id": "b-test1234",
            "product_name": "Horsa-550X-Turbo",
            "qty": 5,
            "user_id": "u-test",
            "status": "requested",
        }
    ]
    
    res = get_booking_updates.invoke({"user_id": "u-test"})
    mock_query.assert_called_once()
    assert len(res) == 1
    assert res[0]["product_name"] == "Horsa-550X-Turbo"
