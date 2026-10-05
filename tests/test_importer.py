from io import BytesIO

from fintrace_api.db import Base
from fintrace_api.importer import import_transactions_csv, parse_amount_minor, parse_timestamp
from fintrace_api.models import Entity, Transaction
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def test_parse_amount_minor_uses_decimal_precision() -> None:
    assert parse_amount_minor("0.29") == 29
    assert parse_amount_minor("500000") == 50_000_000


def test_parse_timestamp_requires_timezone_and_normalizes_to_utc() -> None:
    parsed, source_timezone = parse_timestamp("2026-01-01T15:21:00+05:00")

    assert parsed.isoformat() == "2026-01-01T10:21:00+00:00"
    assert source_timezone == "UTC+05:00"


def test_import_transactions_csv_creates_accounts_and_skips_duplicates() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    header = "transaction_id,source_account,destination_account,amount,currency,timestamp"
    csv_data = f"""{header},transaction_type,channel
tx_001,acc_A,acc_B,10.25,KZT,2026-01-01T10:21:00Z,transfer,mobile
tx_001,acc_A,acc_B,10.25,KZT,2026-01-01T10:21:00Z,transfer,mobile
""".encode()

    with Session(engine) as db:
        imported, skipped, errors = import_transactions_csv(BytesIO(csv_data), db)
        transactions = db.scalars(select(Transaction)).all()
        entities = db.scalars(select(Entity)).all()

    assert imported == 1
    assert skipped == 1
    assert errors == []
    assert transactions[0].amount_minor == 1025
    assert {entity.external_id for entity in entities} == {"acc_A", "acc_B"}
