import pytest

from outcomeos_api.imports import CSV_V1_HEADERS, CsvLimits, parse_csv_v1


def csv_body(row: str = "") -> bytes:
    return ((",".join(CSV_V1_HEADERS)) + "\n" + row).encode()


def test_csv_v1_accepts_strict_public_event() -> None:
    row = (
        "evt-1,order.created,2026-08-15T00:00:00Z,order,ord-1,true,false,"
        'fulfillment,{},{},100,USD,"{""safe"":true}"\n'
    )
    events = parse_csv_v1(csv_body(row), CsvLimits(10000, 10, 20, 1000))
    assert events[0].provider_event_id == "evt-1"
    assert events[0].money and events[0].money.minor_units == 100


@pytest.mark.parametrize(
    "body,code",
    [
        (b"bad,bad\n", "csv_header_invalid"),
        (b"\xff", "csv_utf8_required"),
    ],
)
def test_csv_rejects_invalid_encoding_or_headers(body: bytes, code: str) -> None:
    with pytest.raises(ValueError, match=code):
        parse_csv_v1(body, CsvLimits(1000, 10, 20, 100))


def test_csv_rejects_forbidden_unexpected_server_fields() -> None:
    headers = list(CSV_V1_HEADERS) + ["tenant_id"]
    with pytest.raises(ValueError, match="csv_header_invalid"):
        parse_csv_v1((",".join(headers) + "\n").encode(), CsvLimits(1000, 10, 20, 100))
