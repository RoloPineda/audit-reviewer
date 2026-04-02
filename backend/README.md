# Compliance Audit Tool - Backend

Evaluates healthcare policy documents (P&Ps) against DHCS audit questionnaires using RAG and LLM-based compliance assessment.

## How It Works

1. **Policy documents** are pre-processed into chunks and embedded using Voyage AI's `voyage-law-2` model, stored in ChromaDB.
2. **User uploads** a questionnaire PDF (e.g. DHCS Submission Review Form). The app extracts structured questions via regex-based parsing.
3. **For each question**, the app retrieves the most relevant policy chunks via vector similarity search, then asks Claude to determine whether the requirement is met, with supporting evidence and citations.

## Prerequisites

- Python 3.13
- [uv](https://docs.astral.sh/uv/)
- Docker (for deployment)

## Setup

```bash
cd backend
uv venv --python 3.13
uv sync
uv pip install -e .
```

Create a `.env` file:

```
VOYAGE_API_KEY=your_key
ANTHROPIC_API_KEY=your_key
AUTH_USERNAME=your_username
AUTH_PASSWORD=your_password
```

## Running

```bash
source .env
uv run uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## API Endpoints

All endpoints except health check require HTTP Basic Auth.

| Method | Path                 | Auth | Description                          |
|--------|----------------------|------|--------------------------------------|
| GET    | `/api/health`        | No   | Health check, ChromaDB availability  |
| POST   | `/api/questionnaire` | Yes  | Upload questionnaire PDF, extract questions |
| POST   | `/api/evaluate`      | Yes  | Evaluate a single question against policies |

### POST /api/questionnaire

Upload a PDF file as multipart form data. Returns extracted questions.

```bash
curl -u user:pass -F "file=@data/questionnaire/audit_questions.pdf" http://localhost:8000/api/questionnaire
```

Response:
```json
{
  "metadata": {
    "submission_item": "Policy and Procedure (P&P) regarding APL 25-008: ...",
    "apl_reference": "APL 25-008"
  },
  "questions": [
    {
      "number": 1,
      "text": "Does the P&P state that...",
      "reference": "APL 25-008, page 1"
    }
  ]
}
```

### POST /api/evaluate

Evaluate a single question. Send JSON body with the question text.

```bash
curl -u user:pass -X POST http://localhost:8000/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{"question": "Does the P&P state MCPs must not deny hospice care?"}'
```

Response:
```json
{
  "status": "met",
  "evidence": "The policy states...",
  "citation": "GG.1503, POLICY.A, page 1"
}
```

Status values: `met`, `not_met`, `partially_met`, `error`.

## Scripts

Run from the `backend/` directory.

| Script | Purpose |
|--------|---------|
| `scripts/verify_sections.py` | Verify all P&P PDFs have PURPOSE, POLICY, PROCEDURE sections |
| `scripts/preprocess.py` | Extract chunks from P&P PDFs and embed into ChromaDB |
| `scripts/verify_retrieval.py` | Test vector search quality against sample questions |
| `scripts/verify_evaluation.py` | Test full RAG + LLM pipeline on sample questions |
| `scripts/search_chunks.py` | Keyword search through chunks for spot-checking |

### Preprocessing

To re-process the policy documents (only needed if policies change):

```bash
# Dry run first to verify extraction
uv run scripts/preprocess.py data/policies data/processed --dry-run

# Full run with embedding
source .env
uv run scripts/preprocess.py data/policies data/processed
```

## Testing

```bash
uv run pytest tests/ -v
```

## Project Structure

```
backend/
  app/
    main.py                  # FastAPI application
    services/
      evaluator.py           # RAG retrieval + LLM evaluation
      questionnaire.py       # PDF question extraction
  data/
    policies/                # Raw P&P PDFs (gitignored)
    processed/
      chroma/                # Embedded chunks (committed)
      chunks_preview.json    # Dry run output (gitignored)
    questionnaire/           # Sample audit PDFs
  scripts/                   # Preprocessing and verification
  tests/                     # Pytest tests
  Dockerfile
  pyproject.toml
```

## Deployment

Build and test locally:

```bash
docker build -t audit-tool .
docker run -p 8000:8000 --env-file .env audit-tool
```

Deploy to Render:

1. Push to GitHub
2. Create a Web Service on Render, set root directory to `backend/`
3. Render detects the Dockerfile automatically
4. Add environment variables: `VOYAGE_API_KEY`, `ANTHROPIC_API_KEY`, `AUTH_USERNAME`, `AUTH_PASSWORD`
5. Deploy

## Tech Stack

- **Framework:** FastAPI
- **Embeddings:** Voyage AI voyage-law-2
- **Vector store:** ChromaDB (persistent, bundled in container)
- **LLM:** Claude Haiku 4.5 via Anthropic API
- **PDF parsing:** PyMuPDF