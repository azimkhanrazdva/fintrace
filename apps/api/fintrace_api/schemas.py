from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EntityType(StrEnum):
    person = "Person"
    organization = "Organization"
    account = "Account"
    merchant = "Merchant"
    device = "Device"
    ip = "IP"
    email = "Email"
    phone = "Phone"
    address = "Address"
    bank = "Bank"
    transaction = "Transaction"


class EntityRead(BaseModel):
    id: int
    external_id: str
    entity_type: EntityType
    display_name: str

    model_config = ConfigDict(from_attributes=True)


class TransactionRead(BaseModel):
    transaction_id: str
    source_account: str
    destination_account: str
    amount_minor: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    timestamp_utc: datetime
    source_timezone: str | None = None
    transaction_type: str
    channel: str

    model_config = ConfigDict(from_attributes=True)


class ImportResult(BaseModel):
    imported: int
    skipped_duplicates: int
    errors: list[str]


class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    risk: int = 0


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    amount_minor: int | None = None
    timestamp_utc: datetime | None = None


class PatternRead(BaseModel):
    pattern_type: str
    entities: list[str]
    transactions: list[str]
    time_window: dict[str, str]
    score: float
    evidence_ids: list[str]
    parameters: dict[str, int | float | str]


class EvidenceRead(BaseModel):
    evidence_id: str
    type: str
    transaction_ids: list[str]
    description: str


class RiskComponent(BaseModel):
    signal: str
    contribution: int
    evidence_ids: list[str]


class RiskRead(BaseModel):
    risk_score: int
    components: list[RiskComponent]


class CaseRead(BaseModel):
    case_id: str
    seed: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    patterns: list[PatternRead]
    evidence: list[EvidenceRead]
    risk: RiskRead
    excluded_count: int = 0
    expansion_reasoning: list[str]
