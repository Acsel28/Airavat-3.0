# Tier 8 Loan Offer Generation & Negotiation Agent

Self-contained Python module for local, terminal-based loan retrieval, deterministic offer generation, and optional stateful negotiation.

## Setup

1. Create an isolated environment inside this folder:
   ```bash
   cd loans8
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   Fill `GOOGLE_API_KEY` using a free key from https://aistudio.google.com/app/apikey
4. Run one-time datastore setup:
   ```bash
   python setup_once.py
   ```
5. Start the CLI app (without re-running setup):
   ```bash
   python main.py
   ```

## Optional setup flags

- `python main.py --setup` runs setup and starts the app in one command.

## Notes

- Embeddings are generated using Gemini API (`gemini-embedding-001`) instead of local Hugging Face models.
- The embedding path batches requests and uses in-process caching to minimize API calls.
- Built-in rate limiting is enabled for Gemini calls. You can tune caps with:
  - `EMBEDDING_API_MAX_REQUESTS_PER_MIN` (default `20`)
  - `NEGOTIATION_API_MAX_REQUESTS_PER_MIN` (default `12`)
  - `NEGOTIATION_MAX_LLM_CALLS_PER_SESSION` (default `4`)
- `.venv` is local to `loans8`, so it does not affect any Python environment outside this folder.
