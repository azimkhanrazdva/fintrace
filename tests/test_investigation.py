from datetime import UTC, datetime

from fintrace_api.investigation import build_case
from fintrace_api.models import Transaction


def tx(
    transaction_id: str,
    source: str,
    destination: str,
    amount_minor: int,
    minute: int,
) -> Transaction:
    return Transaction(
        transaction_id=transaction_id,
        source_account=source,
        destination_account=destination,
        amount_minor=amount_minor,
        currency="KZT",
        timestamp_utc=datetime(2026, 1, 1, 10, minute, tzinfo=UTC),
        source_timezone="UTC",
        transaction_type="transfer",
        channel="mobile",
    )


def test_build_case_detects_patterns_and_explains_risk() -> None:
    case = build_case(
        "acc_A",
        [
            tx("tx_001", "acc_A", "acc_B", 500_000, 1),
            tx("tx_002", "acc_B", "acc_C", 498_000, 12),
            tx("tx_003", "acc_A", "acc_D", 100_000, 13),
            tx("tx_004", "acc_A", "acc_E", 100_000, 14),
            tx("tx_005", "acc_C", "acc_A", 490_000, 30),
            tx("tx_999", "acc_X", "acc_Y", 1_000, 31),
        ],
    )

    pattern_types = {pattern.pattern_type for pattern in case.patterns}

    assert case.case_id == "case_acc_A"
    assert {"rapid_pass_through", "fan_out", "circular_flow"} <= pattern_types
    assert case.risk.risk_score > 0
    assert case.evidence
    assert case.excluded_count == 1
