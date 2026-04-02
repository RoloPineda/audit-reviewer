"""FastAPI application for the compliance audit tool.

Provides endpoints for uploading questionnaire PDFs and evaluating
individual audit questions against the pre-embedded policy corpus.

Endpoints:
    GET  /api/health          - Health check (public)
    POST /api/questionnaire   - Upload questionnaire PDF (auth required)
    POST /api/evaluate        - Evaluate a single question (auth required)

Usage:
    AUTH_USERNAME=user AUTH_PASSWORD=pass \
    VOYAGE_API_KEY=key ANTHROPIC_API_KEY=key \
    uvicorn app.main:app --reload
"""

import logging
import os
import secrets
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from app.services.evaluator import Evaluator
from app.services.questionnaire import extract_questions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

CHROMA_PATH = os.environ.get(
    "CHROMA_PATH",
    str(Path(__file__).parent.parent / "data" / "processed" / "chroma"),
)
AUTH_USERNAME = os.environ.get("AUTH_USERNAME", "")
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "")

security = HTTPBasic()
evaluator: Evaluator | None = None


class EvaluateRequest(BaseModel):
    """Request body for the evaluate endpoint."""

    question: str


class EvaluateResponse(BaseModel):
    """Response body for the evaluate endpoint."""

    status: str
    evidence: str
    citation: str


class QuestionnaireResponse(BaseModel):
    """Response body for the questionnaire upload endpoint."""

    metadata: dict
    questions: list[dict]


def verify_credentials(
    credentials: HTTPBasicCredentials = Depends(security),
) -> str:
    """Verify basic auth credentials against environment variables.

    Uses timing-safe comparison to prevent timing attacks.

    Args:
        credentials: The username and password from the request.

    Returns:
        The authenticated username.

    Raises:
        HTTPException: If credentials are invalid or not configured.
    """
    if not AUTH_USERNAME or not AUTH_PASSWORD:
        raise HTTPException(
            status_code=500,
            detail="Auth not configured on server.",
        )

    username_ok = secrets.compare_digest(
        credentials.username.encode(), AUTH_USERNAME.encode()
    )
    password_ok = secrets.compare_digest(
        credentials.password.encode(), AUTH_PASSWORD.encode()
    )

    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials.",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username


def get_evaluator() -> Evaluator:
    """Lazy-initialize the evaluator on first use.

    Returns:
        The singleton Evaluator instance.

    Raises:
        HTTPException: If the evaluator cannot be initialized.
    """
    global evaluator  # noqa: PLW0603
    if evaluator is None:
        try:
            evaluator = Evaluator(chroma_path=CHROMA_PATH)
        except ValueError as e:
            logger.error("Evaluator config error: %s", e)
            raise HTTPException(
                status_code=500,
                detail=f"Configuration error: {e}",
            ) from e
        except RuntimeError as e:
            logger.error("Evaluator initialization failed: %s", e)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to load policy data: {e}",
            ) from e
    return evaluator


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Validate configuration on startup.

    Checks that required environment variables are set and that the
    ChromaDB collection is accessible before accepting requests.
    """
    missing = []
    if not os.environ.get("VOYAGE_API_KEY"):
        missing.append("VOYAGE_API_KEY")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")
    if not AUTH_USERNAME or not AUTH_PASSWORD:
        missing.append("AUTH_USERNAME/AUTH_PASSWORD")

    if missing:
        logger.error("Missing environment variables: %s", ", ".join(missing))

    chroma_dir = Path(CHROMA_PATH)
    if not chroma_dir.exists():
        logger.error("ChromaDB directory not found: %s", CHROMA_PATH)
    else:
        logger.info("ChromaDB directory: %s", CHROMA_PATH)

    yield


app = FastAPI(
    title="Compliance Audit Tool",
    description="Evaluate P&P compliance against DHCS audit questionnaires",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> dict:
    """Health check endpoint.

    Returns:
        A dict with status and ChromaDB availability.
    """
    chroma_ok = Path(CHROMA_PATH).exists()
    return {
        "status": "ok" if chroma_ok else "degraded",
        "chroma_path": CHROMA_PATH,
        "chroma_available": chroma_ok,
    }


@app.post("/api/questionnaire", response_model=QuestionnaireResponse)
async def upload_questionnaire(
    file: UploadFile = File(...),
    _username: str = Depends(verify_credentials),
) -> dict:
    """Upload a questionnaire PDF and extract structured questions.

    Args:
        file: The uploaded PDF file.

    Returns:
        A dict with metadata and a list of extracted questions.

    Raises:
        HTTPException: If the file is not a PDF or no questions are found.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF.")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = extract_questions(tmp_path)
    except Exception as e:
        logger.exception("Failed to extract questions from %s", file.filename)
        raise HTTPException(
            status_code=422,
            detail=f"Failed to parse PDF: {e}",
        ) from e
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if not result["questions"]:
        raise HTTPException(
            status_code=422,
            detail="No audit questions found in the uploaded PDF.",
        )

    logger.info(
        "Extracted %d questions from %s",
        len(result["questions"]),
        file.filename,
    )
    return result


@app.post("/api/evaluate", response_model=EvaluateResponse)
def evaluate_question(
    request: EvaluateRequest,
    _username: str = Depends(verify_credentials),
) -> dict:
    """Evaluate a single audit question against the policy corpus.

    Args:
        request: The question to evaluate.

    Returns:
        A dict with status, evidence, and citation.
    """
    ev = get_evaluator()
    result = ev.evaluate_question(request.question)

    if result["status"] == "error":
        logger.warning(
            "Evaluation returned error for: %s", request.question[:80]
        )

    return {
        "status": result.get("status", "error"),
        "evidence": result.get("evidence", ""),
        "citation": result.get("citation", ""),
    }