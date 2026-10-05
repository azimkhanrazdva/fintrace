from collections import Counter, defaultdict, deque
from datetime import timedelta

from fintrace_api.models import Transaction
from fintrace_api.schemas import (
    CaseRead,
    EvidenceRead,
    GraphEdge,
    GraphNode,
    PatternRead,
    RiskComponent,
    RiskRead,
)


def build_case(seed: str, transactions: list[Transaction]) -> CaseRead:
    related = _expand(seed, transactions)
    patterns = _detect_patterns(related)
    evidence = _build_evidence(patterns, related)
    risk = _score(patterns)
    accounts = sorted(
        {tx.source_account for tx in related} | {tx.destination_account for tx in related}
    )
    nodes = [
        GraphNode(
            id=account,
            type="Account",
            label=account,
            risk=risk.risk_score if account == seed else 0,
        )
        for account in accounts
    ]
    edges = [
        GraphEdge(
            id=tx.transaction_id,
            source=tx.source_account,
            target=tx.destination_account,
            type="TRANSFERRED_TO",
            amount_minor=tx.amount_minor,
            timestamp_utc=tx.timestamp_utc,
        )
        for tx in related
    ]
    return CaseRead(
        case_id=f"case_{seed}",
        seed=seed,
        nodes=nodes,
        edges=edges,
        patterns=patterns,
        evidence=evidence,
        risk=risk,
        excluded_count=max(len(transactions) - len(related), 0),
        expansion_reasoning=[
            "Included transactions where the seed account sends or receives funds.",
            "Included one-hop counterparties so the case graph stays small enough to inspect.",
        ],
    )


def _expand(seed: str, transactions: list[Transaction]) -> list[Transaction]:
    direct = [
        tx
        for tx in transactions
        if tx.source_account == seed or tx.destination_account == seed
    ]
    neighbors = {seed}
    for tx in direct:
        neighbors.add(tx.source_account)
        neighbors.add(tx.destination_account)
    return [
        tx
        for tx in transactions
        if tx.source_account in neighbors and tx.destination_account in neighbors
    ]


def _detect_patterns(transactions: list[Transaction]) -> list[PatternRead]:
    return [
        *_rapid_pass_through(transactions),
        *_fan(transactions, "fan_out"),
        *_fan(transactions, "fan_in"),
        *_cycles(transactions),
    ]


def _rapid_pass_through(transactions: list[Transaction]) -> list[PatternRead]:
    by_account: dict[str, list[Transaction]] = defaultdict(list)
    for tx in transactions:
        by_account[tx.destination_account].append(tx)
        by_account[tx.source_account].append(tx)

    patterns: list[PatternRead] = []
    for account, account_txs in by_account.items():
        incoming = [tx for tx in account_txs if tx.destination_account == account]
        outgoing = [tx for tx in account_txs if tx.source_account == account]
        for in_tx in incoming:
            for out_tx in outgoing:
                delta = out_tx.timestamp_utc - in_tx.timestamp_utc
                if timedelta(0) <= delta <= timedelta(minutes=30):
                    ratio = min(in_tx.amount_minor, out_tx.amount_minor) / max(
                        in_tx.amount_minor,
                        out_tx.amount_minor,
                    )
                    if ratio >= 0.9:
                        patterns.append(
                            _pattern(
                                "rapid_pass_through",
                                [account],
                                [in_tx, out_tx],
                                min(1.0, ratio),
                                {"max_time_minutes": 30, "amount_similarity": 0.9},
                            )
                        )
    return patterns


def _fan(transactions: list[Transaction], pattern_type: str) -> list[PatternRead]:
    attr = "source_account" if pattern_type == "fan_out" else "destination_account"
    groups: dict[str, list[Transaction]] = defaultdict(list)
    for tx in transactions:
        groups[getattr(tx, attr)].append(tx)

    patterns: list[PatternRead] = []
    for account, account_txs in groups.items():
        counterparties = {
            tx.destination_account if pattern_type == "fan_out" else tx.source_account
            for tx in account_txs
        }
        if len(counterparties) >= 3:
            patterns.append(
                _pattern(
                    pattern_type,
                    [account, *sorted(counterparties)],
                    account_txs,
                    min(1.0, len(counterparties) / 5),
                    {"min_counterparties": 3},
                )
            )
    return patterns


def _cycles(transactions: list[Transaction]) -> list[PatternRead]:
    graph: dict[str, list[Transaction]] = defaultdict(list)
    for tx in transactions:
        graph[tx.source_account].append(tx)

    patterns: list[PatternRead] = []
    for start in graph:
        queue = deque([(start, [], {start})])
        while queue:
            account, path, seen = queue.popleft()
            if len(path) >= 4:
                continue
            for tx in graph.get(account, []):
                if tx.destination_account == start and path:
                    cycle = [*path, tx]
                    patterns.append(
                        _pattern(
                            "circular_flow",
                            sorted({edge.source_account for edge in cycle} | {start}),
                            cycle,
                            min(1.0, len(cycle) / 4),
                            {"max_depth": 4},
                        )
                    )
                elif tx.destination_account not in seen:
                    queue.append(
                        (tx.destination_account, [*path, tx], seen | {tx.destination_account})
                    )
    unique: dict[tuple[str, ...], PatternRead] = {}
    for pattern in patterns:
        unique[tuple(sorted(pattern.transactions))] = pattern
    return list(unique.values())


def _pattern(
    pattern_type: str,
    entities: list[str],
    transactions: list[Transaction],
    score: float,
    parameters: dict[str, int | float | str],
) -> PatternRead:
    start = min(tx.timestamp_utc for tx in transactions)
    end = max(tx.timestamp_utc for tx in transactions)
    tx_ids = [tx.transaction_id for tx in transactions]
    return PatternRead(
        pattern_type=pattern_type,
        entities=entities,
        transactions=tx_ids,
        time_window={"start": start.isoformat(), "end": end.isoformat()},
        score=round(score, 3),
        evidence_ids=[f"ev_{tx_id}" for tx_id in tx_ids],
        parameters=parameters,
    )


def _build_evidence(
    patterns: list[PatternRead],
    transactions: list[Transaction],
) -> list[EvidenceRead]:
    descriptions = {
        tx.transaction_id: (
            f"{tx.source_account} sent {tx.amount_minor} minor units to "
            f"{tx.destination_account} at {tx.timestamp_utc.isoformat()}."
        )
        for tx in transactions
    }
    used = Counter(tx_id for pattern in patterns for tx_id in pattern.transactions)
    return [
        EvidenceRead(
            evidence_id=f"ev_{tx_id}",
            type="transaction",
            transaction_ids=[tx_id],
            description=descriptions[tx_id],
        )
        for tx_id in sorted(used)
    ]


def _score(patterns: list[PatternRead]) -> RiskRead:
    weights = {
        "rapid_pass_through": 28,
        "circular_flow": 24,
        "fan_out": 16,
        "fan_in": 16,
    }
    components = [
        RiskComponent(
            signal=pattern.pattern_type,
            contribution=round(weights.get(pattern.pattern_type, 8) * pattern.score),
            evidence_ids=pattern.evidence_ids,
        )
        for pattern in patterns
    ]
    score = min(sum(component.contribution for component in components), 100)
    return RiskRead(risk_score=score, components=components)
