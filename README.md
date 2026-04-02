# Compliance Audit Tool

Automates the evaluation of healthcare Policy & Procedure (P&P) documents against DHCS audit questionnaires. Upload a questionnaire PDF, and the tool checks each requirement against 370 pre-embedded policy documents, returning whether each requirement is met with supporting evidence and citations.


## Demo

- **Frontend:** [deployed-url]
- **Backend:** [deployed-url]

## How It Works

1. **Policy documents** (370 P&P PDFs from CalOptima Health) are pre-processed into ~5,500 text chunks, embedded using Voyage AI's `voyage-law-2` model, and stored in ChromaDB.
2. **User uploads** a DHCS audit questionnaire PDF. The app extracts structured questions via regex-based parsing of the standardized form format.
3. **For each question**, the app retrieves the most relevant policy chunks via vector similarity search, then asks Claude (Haiku 4.5) to determine whether the requirement is met, returning a binary Yes/No assessment with evidence and citations matching the DHCS form format.

## Architecture

```
User uploads PDF
        |
        v
  [React Frontend]  ----->  [FastAPI Backend]
   (Vercel)                   (Render/Docker)
                                    |
                          +---------+---------+
                          |                   |
                     [ChromaDB]          [Claude API]
                    (embedded in         (Haiku 4.5)
                     container)
                          |
                    [Voyage AI]
                   (voyage-law-2
                    embeddings)
```

## Project Structure

```
readily-takehome/
  backend/                   # FastAPI + ChromaDB + evaluation pipeline
    app/
      main.py                # API endpoints
      services/
        evaluator.py         # RAG retrieval + LLM evaluation
        questionnaire.py     # PDF question extraction
    data/
      processed/chroma/      # Pre-embedded policy chunks
    scripts/                 # Preprocessing and verification
    tests/
    Dockerfile
  frontend/                  # React + React Spectrum
    src/
      pages/                 # Login, Upload, Results
      context/               # Auth state
      api.js                 # API client
```

See [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for setup and usage.

## Quick Start

### Backend

```bash
cd backend
uv venv --python 3.13
uv sync && uv pip install -e .

# Set environment variables
export VOYAGE_API_KEY=your_key
export ANTHROPIC_API_KEY=your_key
export AUTH_USERNAME=your_user
export AUTH_PASSWORD=your_pass

uv run uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
echo "VITE_API_URL=http://localhost:8000" > .env
npm run dev
```

## Design Decisions

**Binary met/not_met over a three-way split.** The DHCS audit form uses Yes/No checkboxes. Adding "partially met" would introduce a status that doesn't map to the real workflow.

**Voyage AI voyage-law-2 for embeddings.** Purpose-built for legal and regulatory text. Outperforms general-purpose embedding models on this domain. 50M free tokens covers our corpus many times over.

**Haiku over Sonnet.** Fast and cheap enough to evaluate 64 questions sequentially without timeout issues. Evaluation quality is strong with a well-tuned prompt. Sonnet is available as a one-line config change if needed.

**ChromaDB bundled in the container.** No external database to manage. The policy corpus is a fixed, known set that changes infrequently. Pre-embedding at build time means zero runtime preprocessing cost.

**Per-question evaluation over batch.** Each question is a separate API call. Avoids timeout issues on free-tier hosting, gives the user incremental progress, and simplifies error handling.

## Future Improvements

### Policy Selection

The app currently searches all 5,458 chunks for every question. A production version would let users select which policies are relevant, or auto-detect based on the APL reference. The hospice questionnaire (APL 25-008) should primarily search GG.1503 and related hospice policies, not all 370 documents. This improves accuracy by reducing noise and speeds up retrieval.

### Workflow and State

Auditors don't finish 64 questions in one sitting. A functional app needs persistent sessions: save progress, resume later, track which questions have been reviewed. Each question should support an auditor override (change the AI's determination) and manual notes.

### Export

The end product of an audit is the filled-out DHCS Submission Review Form with Yes/No answers and citations. The app should generate a PDF or Excel matching the original form format so the auditor can submit it directly.


### Confidence and Transparency

Auditors need to trust the tool before relying on it. Showing retrieval confidence scores, which policy chunks were considered, and letting users view the raw policy text alongside the AI assessment would build that trust. A side-by-side view of the question, the retrieved policy passage, and the AI's reasoning would be the ideal interface.

### Gap Remediation

When a requirement is "not met," the compliance team needs to know what to add to their P&P. The app could suggest draft policy language based on the APL requirement, turning a compliance gap into an actionable task.

### Hybrid Search

Pure vector search misses some matches where the policy uses different terminology than the question (e.g., "shall ensure provision" vs. "must not deny"). Adding keyword search (BM25) alongside vector similarity would catch these cases and improve recall.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | React 19, Adobe React Spectrum, Vite |
| Backend | Python 3.13, FastAPI, uv |
| Vector Store | ChromaDB (persistent, bundled) |
| Embeddings | Voyage AI voyage-law-2 |
| LLM | Claude Haiku 4.5 (Anthropic API) |
| PDF Parsing | PyMuPDF |
| Auth | HTTP Basic Auth |
| Deployment | Render (backend), Vercel (frontend) |