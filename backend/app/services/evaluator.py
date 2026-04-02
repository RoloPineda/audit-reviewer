"""Evaluate audit questions against policy documents using RAG + LLM.

For each audit question, retrieves the most relevant policy chunks from
ChromaDB using vector similarity search, then asks an LLM to determine
whether the requirement is met based on the retrieved evidence.

The LLM returns a structured assessment: met/not_met/partially_met,
the specific evidence passage, and the source citation.

Usage:
    from app.services.evaluator import Evaluator

    evaluator = Evaluator(chroma_path="data/processed/chroma")
    result = evaluator.evaluate_question(
        "Does the P&P state MCPs must not deny hospice care to Members "
        "certified as terminally ill?"
    )
    result["status"]    # "met", "not_met", or "partially_met"
    result["evidence"]  # the specific policy passage
    result["citation"]  # e.g. "GG.1503, POLICY.B, page 2"
"""

import json
import logging
import os

import anthropic
import chromadb
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)

LLM_TIMEOUT = 30.0
LLM_MAX_RETRIES = 3

SYSTEM_PROMPT = """\
You are a healthcare compliance auditor. You will be given an audit \
question and a set of policy document excerpts. Your task is to determine \
whether the policy documents satisfy the requirement stated in the question.

Respond with a JSON object containing exactly these fields:
- "status": one of "met", "not_met", or "partially_met"
- "evidence": the specific passage from the policy that addresses the \
requirement. Quote the relevant text directly. If not met, explain what \
is missing.
- "citation": the source document in the format \
"POLICY_NUMBER, SECTION.SUBSECTION, page N"

Rules:
- Only use the provided policy excerpts as evidence. Do not infer or \
assume policy content.
- "met" means the policy explicitly addresses all parts of the requirement.
- "partially_met" means the policy addresses some but not all parts.
- "not_met" means none of the provided excerpts address the requirement.
- Be precise. If the question asks about multiple sub-requirements, \
evaluate each one.

Respond with valid JSON only. No other text."""

QUESTION_TEMPLATE = """\
Audit Question:
{question}

Policy Excerpts:
{excerpts}"""


def _format_excerpts(results: dict) -> str:
    """Format ChromaDB query results into labeled policy excerpts.

    Each excerpt is labeled with its source document, section, and page
    so the LLM can reference them in citations.

    Args:
        results: ChromaDB query results dict with ids, documents, metadata.

    Returns:
        A formatted string of labeled policy excerpts.
    """
    parts = []
    for i in range(len(results["ids"][0])):
        meta = results["metadata"][0][i]
        doc = results["documents"][0][i]
        label = (
            f"[{meta['policy_number']}, "
            f"{meta['section']}.{meta['subsection']}, "
            f"page {meta['page']}]"
        )
        parts.append(f"{label}\n{doc}")
    return "\n\n".join(parts)


def _parse_llm_response(text: str) -> dict:
    """Parse the LLM's JSON response into a result dict.

    Handles cases where the LLM wraps JSON in markdown code fences.

    Args:
        text: Raw LLM response text.

    Returns:
        A dict with keys: status, evidence, citation.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0]
    return json.loads(cleaned)


class Evaluator:
    """Evaluates audit questions against policy documents.

    Combines ChromaDB vector retrieval with LLM-based compliance
    assessment to determine whether each audit requirement is met.
    """

    def __init__(
        self,
        chroma_path: str,
        model: str = "claude-haiku-4-5-20251001",
        n_results: int = 7,
    ):
        """Initialize the evaluator with ChromaDB and Anthropic clients.

        Args:
            chroma_path: Path to the ChromaDB persistent storage directory.
            model: Anthropic model ID to use for evaluation.
            n_results: Number of chunks to retrieve per question.

        Raises:
            ValueError: If VOYAGE_API_KEY is not set.
            RuntimeError: If ChromaDB collection cannot be loaded.
        """
        voyage_key = os.environ.get("VOYAGE_API_KEY")
        if not voyage_key:
            raise ValueError("VOYAGE_API_KEY environment variable not set.")

        voyage_ef = embedding_functions.VoyageAIEmbeddingFunction(
            api_key=voyage_key,
            model_name="voyage-law-2",
        )

        try:
            client = chromadb.PersistentClient(path=chroma_path)
            self.collection = client.get_collection(
                name="policy_chunks",
                embedding_function=voyage_ef,
            )
            logger.info(
                "Loaded ChromaDB collection with %d chunks",
                self.collection.count(),
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to load ChromaDB from {chroma_path}: {e}"
            ) from e

        self.anthropic = anthropic.Anthropic(
            timeout=LLM_TIMEOUT,
            max_retries=LLM_MAX_RETRIES,
        )
        self.model = model
        self.n_results = n_results

    def retrieve(self, question: str) -> dict:
        """Retrieve relevant policy chunks for a question.

        Args:
            question: The audit question text.

        Returns:
            ChromaDB query results with ids, documents, metadata, distances.

        Raises:
            RuntimeError: If the retrieval fails.
        """
        try:
            return self.collection.query(
                query_texts=[question],
                n_results=self.n_results,
            )
        except Exception as e:
            logger.exception("Retrieval failed for question: %s", question[:80])
            raise RuntimeError(f"Retrieval failed: {e}") from e

    def evaluate_question(self, question: str) -> dict:
        """Evaluate whether a single audit question is met by the policies.

        Retrieves relevant policy chunks, sends them with the question
        to the LLM, and parses the structured response. Handles LLM
        errors gracefully by returning an error status.

        Args:
            question: The audit question text.

        Returns:
            A dict with keys: status, evidence, citation, chunks_used.
            chunks_used contains the metadata of retrieved chunks for
            transparency. On LLM failure, status is "error".
        """
        results = self.retrieve(question)
        excerpts = _format_excerpts(results)

        try:
            message = self.anthropic.messages.create(
                model=self.model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": QUESTION_TEMPLATE.format(
                            question=question,
                            excerpts=excerpts,
                        ),
                    },
                ],
            )
        except anthropic.RateLimitError:
            logger.warning("Anthropic rate limit hit for question: %s", question[:80])
            return {
                "status": "error",
                "evidence": "Rate limit exceeded. Try again shortly.",
                "citation": "",
                "chunks_used": results["metadata"][0],
            }
        except anthropic.APITimeoutError:
            logger.warning("Anthropic timeout for question: %s", question[:80])
            return {
                "status": "error",
                "evidence": "LLM request timed out. Try again.",
                "citation": "",
                "chunks_used": results["metadata"][0],
            }
        except anthropic.APIError as e:
            logger.exception("Anthropic API error: %s", e)
            return {
                "status": "error",
                "evidence": f"LLM error: {e}",
                "citation": "",
                "chunks_used": results["metadata"][0],
            }

        response_text = message.content[0].text
        logger.debug("LLM response for question: %s", response_text[:200])

        try:
            parsed = _parse_llm_response(response_text)
        except (json.JSONDecodeError, KeyError):
            logger.warning(
                "Failed to parse LLM response: %s", response_text[:200]
            )
            parsed = {
                "status": "error",
                "evidence": response_text,
                "citation": "",
            }

        parsed["chunks_used"] = results["metadata"][0]
        return parsed

    def evaluate_all(self, questions: list[dict]) -> list[dict]:
        """Evaluate a list of audit questions.

        Args:
            questions: List of question dicts with keys: number, text.

        Returns:
            A list of result dicts, each containing: number, question,
            status, evidence, citation, chunks_used.
        """
        results = []
        for q in questions:
            logger.info("Evaluating Q%d...", q["number"])
            evaluation = self.evaluate_question(q["text"])
            results.append({
                "number": q["number"],
                "question": q["text"],
                **evaluation,
            })
        return results