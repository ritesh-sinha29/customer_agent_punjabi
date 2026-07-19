import pytest
from unittest.mock import patch
from src.app.tools.booking_tools import get_canonical_product_name, create_booking

def test_canonical_product_name_exact():
    # Exact matches
    assert get_canonical_product_name("Horsa-550X-Turbo") == "Horsa-550X-Turbo"
    assert get_canonical_product_name("TrioSan Gold") == "TrioSan Gold"
    assert get_canonical_product_name("MaxaPro-DS Dairy") == "MaxaPro-DS Dairy"
    assert get_canonical_product_name("MaxaPro Liquid") == "MaxaPro Liquid"
    assert get_canonical_product_name("Buffalo-Power 2X") == "Buffalo-Power 2X"
    assert get_canonical_product_name("Buffalo-F 1.5X") == "Buffalo-F 1.5X"

def test_canonical_product_name_variations():
    # Case variation
    assert get_canonical_product_name("horsa-550x-turbo") == "Horsa-550X-Turbo"
    assert get_canonical_product_name("triosan gold") == "TrioSan Gold"
    
    # Capitalization & Spaces
    assert get_canonical_product_name("  maxapro-ds dairy  ") == "MaxaPro-DS Dairy"
    assert get_canonical_product_name("MaxaPro-DS") == "MaxaPro-DS Dairy"
    assert get_canonical_product_name("maxapro liquid") == "MaxaPro Liquid"
    
    # Hyphen & Spaces
    assert get_canonical_product_name("Horsa 550X Turbo") == "Horsa-550X-Turbo"
    assert get_canonical_product_name("buffalo-power 2x") == "Buffalo-Power 2X"
    assert get_canonical_product_name("buffalo power") == "Buffalo-Power 2X"
    
    # Decimal and letter variations
    assert get_canonical_product_name("buffalo f 1.5x") == "Buffalo-F 1.5X"
    assert get_canonical_product_name("buffalo f1.5x") == "Buffalo-F 1.5X"
    assert get_canonical_product_name("buffalo 1.5") == "Buffalo-F 1.5X"

def test_canonical_product_name_punjabi():
    # Punjabi matching
    assert get_canonical_product_name("ਮੈਕਸਾਪ੍ਰੋ ਲਿਕਵਿਡ") == "MaxaPro Liquid"
    assert get_canonical_product_name("ਟ੍ਰੀਓਸੈਨ ਗੋਲਡ") == "TrioSan Gold"
    assert get_canonical_product_name("ਹੋਰਸਾ 550") == "Horsa-550X-Turbo"
    assert get_canonical_product_name("ਬਫਲੋ ਪਾਵਰ") == "Buffalo-Power 2X"
    assert get_canonical_product_name("ਬਫਲੋ ਐਫ") == "Buffalo-F 1.5X"

def test_canonical_product_name_typos():
    # Minor typos
    assert get_canonical_product_name("Hors-550X-Turbo") == "Horsa-550X-Turbo"
    assert get_canonical_product_name("Triosn Gold") == "TrioSan Gold"
    assert get_canonical_product_name("MaxaPr Liquid") == "MaxaPro Liquid"

def test_canonical_product_name_invalid():
    # Completely invalid names (should raise ValueError)
    with pytest.raises(ValueError) as excinfo:
        get_canonical_product_name("abcd")
    assert "Invalid product name 'abcd'" in str(excinfo.value)
    assert "Horsa-550X-Turbo" in str(excinfo.value)
    assert "TrioSan Gold" in str(excinfo.value)

    with pytest.raises(ValueError):
        get_canonical_product_name("")

@patch("src.app.tools.booking_tools.db_service.execute_insert")
def test_create_booking_valid(mock_insert):
    # Mocking database response
    mock_insert.return_value = {
        "id": "b-test1234",
        "product_name": "Horsa-550X-Turbo",
        "qty": 5,
        "user_id": "u-test",
        "status": "requested",
    }
    
    # Try with a variation ("horsa 550x")
    res = create_booking(user_id="u-test", product_name="horsa 550x", qty=5)
    
    # Check database was called with canonical name
    mock_insert.assert_called_once()
    args, kwargs = mock_insert.call_args
    # First argument is SQL, second argument is params tuple
    params = args[1]
    assert params[1] == "Horsa-550X-Turbo"
    assert params[2] == 5
    assert params[3] == "u-test"
    assert res["product_name"] == "Horsa-550X-Turbo"

@patch("src.app.tools.booking_tools.db_service.execute_insert")
def test_create_booking_invalid(mock_insert):
    with pytest.raises(ValueError) as excinfo:
        create_booking(user_id="u-test", product_name="abcd", qty=10)
    
    # Ensure database was NOT called
    mock_insert.assert_not_called()
    assert "Invalid product name 'abcd'" in str(excinfo.value)
