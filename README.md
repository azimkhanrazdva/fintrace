# FinTrace

**Explainable Graph Intelligence for Financial Investigations**

FinTrace is an open-source graph intelligence platform for exploring suspicious financial activity and building explainable investigation cases from connected transaction data.

FinTrace is a research and engineering project. It is not a production AML compliance system and should not be used as the sole basis for financial or legal decisions.

## Current Release

FinTrace currently ships as a local investigation MVP:

- CSV transaction import.
- UTC-normalized temporal transaction storage.
- Account graph construction from imported transactions.
- Case graph expansion from a seed account.
- Structural detectors for rapid pass-through, fan-in, fan-out, and circular flow.
- Evidence IDs attached to risk signals.
- Investigation-priority scoring from computed signals.
- JSON case export.
- React workspace for seed selection, case graph review, evidence, and export.

Benchmark: pending.

## Run Locally

```bash
cp .env.example .env
docker compose up --build
```

Then open:

- API: http://localhost:8000/docs
- Web: http://localhost:3000

## API Quick Start

Import transactions from CSV:

```bash
curl -X POST http://localhost:8000/api/v1/transactions/import \
  -F "file=@examples/transactions.csv"
```

Expected CSV columns:

```text
transaction_id,source_account,destination_account,amount,currency,timestamp,transaction_type,channel
```

Amounts are parsed as decimal major units and stored as integer minor units. For example, `123.45` KZT is stored as `12345`.

Open a case graph:

```bash
curl http://localhost:8000/api/v1/cases/acc_A/graph
```

Export a case:

```bash
curl http://localhost:8000/api/v1/cases/acc_A/export -o case_acc_A.json
```

## Safety Language

FinTrace does not automatically label people or organizations as criminals, fraudsters, or money launderers. It surfaces suspicious activity, risk signals, detected structural patterns, and investigation hypotheses that require analyst review.

## Repository Layout

```text
apps/
  api/
  web/
examples/
tests/
docker-compose.yml
pyproject.toml
```

## Not Included Yet

FinTrace does not include GNN training, Neo4j persistence, learned fusion, LLM copilot, or production AML workflows in this release. Those pieces need real evaluation and data-governance work before they belong in the product.
