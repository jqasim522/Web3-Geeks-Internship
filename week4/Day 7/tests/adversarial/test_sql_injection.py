"""
tests/adversarial/test_sql_injection.py — SQL injection tests.

# STATUS: OFFLINE-PASS
# RUN: pytest tests/adversarial/test_sql_injection.py -v
# EXPECTED: All payloads handled safely (parameterized queries protect the DB)

Tests that SQLite parameterized queries in rag_lib.py prevent injection.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))

import pytest
import rag_lib as r


SQL_PAYLOADS = [
    "LAH-0004'; DROP TABLE properties;--",
    "LAH-0004' OR '1'='1",
    "LAH-0004' UNION SELECT * FROM properties--",
    "'; DELETE FROM properties WHERE '1'='1",
    "1; DROP TABLE properties",
    "LAH-0004'/**/OR/**/1=1--",
    "LAH-0001' OR 'x'='x'; DROP TABLE properties;--",
]


@pytest.mark.parametrize("payload", SQL_PAYLOADS)
def test_sql_injection_get_property_no_crash(db_conn, payload):
    """get_property with injection payload must not crash or drop tables."""
    result = r.get_property(payload, conn=db_conn)
    assert result is None  # no match expected


@pytest.mark.parametrize("payload", SQL_PAYLOADS)
def test_sql_injection_get_property_db_intact(db_conn, payload):
    """After injection attempt, properties table must still exist."""
    r.get_property(payload, conn=db_conn)
    count = db_conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0]
    assert count > 0, "Properties table was emptied or dropped after injection attempt!"


def test_sql_injection_query_properties_city(db_conn):
    """query_properties with injected city should return empty, not crash."""
    result = r.query_properties(conn=db_conn, city="Lahore'; DROP TABLE properties;--")
    assert isinstance(result, list)
    # No Lahore results found (injection string is not a real city)
    # DB must still be intact
    count = db_conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0]
    assert count > 0


def test_sql_injection_query_properties_area(db_conn):
    result = r.query_properties(conn=db_conn, area_like="DHA'; DROP TABLE properties;--")
    assert isinstance(result, list)
    count = db_conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0]
    assert count > 0


def test_sql_injection_booking_tool_property_id():
    """Booking tool validate_args must reject SQL injection in property_id."""
    from booking_tool import validate_args, ToolCallError
    for payload in SQL_PAYLOADS:
        with pytest.raises(ToolCallError):
            validate_args({
                "property_id": payload,
                "client_name": "X",
                "client_email": "x@x.com",
                "preferred_time": "2026-09-30 15:00",
            })


def test_sql_injection_parse_question_no_crash():
    """parse_question must not crash on SQL injection strings."""
    for payload in SQL_PAYLOADS:
        result = r.parse_question(payload)
        assert isinstance(result, dict)


def test_db_properties_count_unchanged_after_all_injection(db_conn):
    """Final sanity check: all injection attempts together didn't change row count."""
    for payload in SQL_PAYLOADS:
        r.get_property(payload, conn=db_conn)
        r.query_properties(conn=db_conn, city=payload)
    count = db_conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0]
    assert count == 575, f"Row count changed! Expected 575, got {count}"
