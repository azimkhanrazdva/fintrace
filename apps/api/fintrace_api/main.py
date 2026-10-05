import json
from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from fintrace_api.config import settings
from fintrace_api.db import get_db, init_db
from fintrace_api.importer import import_transactions_csv
from fintrace_api.investigation import build_case
from fintrace_api.models import Entity, Transaction
from fintrace_api.schemas import CaseRead, EntityRead, ImportResult, TransactionRead

DbSession = Annotated[Session, Depends(get_db)]
CsvUpload = Annotated[UploadFile, File(...)]

app = FastAPI(
    title="FinTrace API",
    version="0.1.0",
    description="Foundation API for explainable financial investigation workflows.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/entities/{external_id}", response_model=EntityRead)
def get_entity(external_id: str, db: DbSession) -> Entity:
    entity = db.scalar(select(Entity).where(Entity.external_id == external_id))
    if entity is None:
        raise HTTPException(status_code=404, detail="entity not found")
    return entity


@app.get("/api/v1/transactions", response_model=list[TransactionRead])
def list_transactions(db: DbSession) -> list[Transaction]:
    return list(db.scalars(select(Transaction).order_by(Transaction.timestamp_utc)).all())


@app.get("/api/v1/cases/{seed}/graph", response_model=CaseRead)
def get_case_graph(seed: str, db: DbSession) -> CaseRead:
    transactions = list(db.scalars(select(Transaction).order_by(Transaction.timestamp_utc)).all())
    if not transactions:
        raise HTTPException(status_code=404, detail="no transactions loaded")
    case = build_case(seed, transactions)
    if not case.edges:
        raise HTTPException(status_code=404, detail="seed has no transaction neighborhood")
    return case


@app.get("/api/v1/cases/{seed}/export")
def export_case(seed: str, db: DbSession) -> Response:
    case = get_case_graph(seed, db)
    body = json.dumps(case.model_dump(mode="json"), indent=2)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{case.case_id}.json"'},
    )


@app.post("/api/v1/transactions/import", response_model=ImportResult)
def import_transactions(file: CsvUpload, db: DbSession) -> ImportResult:
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="only CSV uploads are supported")
    imported, skipped, errors = import_transactions_csv(file.file, db)
    return ImportResult(imported=imported, skipped_duplicates=skipped, errors=errors)
