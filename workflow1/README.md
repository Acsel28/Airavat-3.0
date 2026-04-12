# Workflow 1 — Loan Onboarding Conversation Agent

## Setup

1. Create and activate a dedicated virtual environment in this folder:
```bash
cd /Users/apple/Desktop/airavat2/Airavat-3.0/workflow1
python3.10 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
```
Fill `GOOGLE_API_KEY_1`, `GOOGLE_API_KEY_2`, `GOOGLE_API_KEY_3`.
For tracing, use `LANGSMITH_TRACING`, `LANGSMITH_ENDPOINT`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`.

## Run

```bash
python main.py
```

## Dry import check

```bash
python -c "from agent.collection_agent import agent_graph"
```

## Verify SQLite audit trail after a run

```bash
sqlite3 workflow1.db "SELECT event_type, phase, timestamp FROM wf1_audit ORDER BY timestamp DESC LIMIT 20;"
```
