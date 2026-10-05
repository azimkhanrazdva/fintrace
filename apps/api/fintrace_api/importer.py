import csv
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from io import TextIOWrapper

from sqlalchemy import select
from sqlalchemy.orm import Session

from fintrace_api.models import Entity, Transaction

REQUIRED_COLUMNS = {
    "transaction_id",
    "source_account",
    "destination_account",
    "amount",
    "currency",
    "timestamp",
    "transaction_type",
    "channel",
}


def parse_amount_minor(value: str, scale: int = 2) -> int:
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"invalid decimal amount: {value}") from exc
    if amount < 0:
        raise ValueError("amount must be non-negative")
    minor = amount * (Decimal(10) ** scale)
    return int(minor.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def parse_timestamp(value: str) -> tuple[datetime, str | None]:
    raw = value.strip()
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    source_timezone = dt.tzname()
    return dt.astimezone(UTC), source_timezone


def mask_identifier(value: str, visible: int = 4) -> str:
    if len(value) <= visible * 2:
        return value[0:1] + "*" * max(len(value) - 2, 0) + value[-1:]
    return f"{value[:visible]}{'*' * 8}{value[-visible:]}"


def _ensure_account(db: Session, account_id: str, pending_accounts: set[str]) -> None:
    if account_id in pending_accounts:
        return
    exists = db.scalar(
        select(Entity).where(Entity.external_id == account_id, Entity.entity_type == "Account")
    )
    if exists:
        pending_accounts.add(account_id)
        return
    db.add(
        Entity(
            external_id=account_id,
            entity_type="Account",
            display_name=mask_identifier(account_id),
        )
    )
    pending_accounts.add(account_id)


def import_transactions_csv(file_obj, db: Session) -> tuple[int, int, list[str]]:
    reader = csv.DictReader(TextIOWrapper(file_obj, encoding="utf-8-sig"))
    missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
    if missing:
        return 0, 0, [f"missing columns: {', '.join(sorted(missing))}"]

    imported = 0
    skipped = 0
    errors: list[str] = []
    seen: set[str] = set()
    pending_accounts: set[str] = set()

    for line_number, row in enumerate(reader, start=2):
        tx_id = (row.get("transaction_id") or "").strip()
        if not tx_id:
            errors.append(f"line {line_number}: transaction_id is required")
            continue
        duplicate = tx_id in seen or db.scalar(
            select(Transaction).where(Transaction.transaction_id == tx_id)
        )
        if duplicate:
            skipped += 1
            continue
        seen.add(tx_id)

        try:
            timestamp_utc, source_timezone = parse_timestamp(row["timestamp"])
            amount_minor = parse_amount_minor(row["amount"])
        except (ValueError, KeyError) as exc:
            errors.append(f"line {line_number}: {exc}")
            continue

        source = row["source_account"].strip()
        destination = row["destination_account"].strip()
        if not source or not destination:
            errors.append(
                f"line {line_number}: source_account and destination_account are required"
            )
            continue

        _ensure_account(db, source, pending_accounts)
        _ensure_account(db, destination, pending_accounts)
        db.add(
            Transaction(
                transaction_id=tx_id,
                source_account=source,
                destination_account=destination,
                amount_minor=amount_minor,
                currency=row["currency"].strip().upper(),
                timestamp_utc=timestamp_utc,
                source_timezone=source_timezone,
                transaction_type=row["transaction_type"].strip(),
                channel=row["channel"].strip(),
            )
        )
        imported += 1

    db.commit()
    return imported, skipped, errors
