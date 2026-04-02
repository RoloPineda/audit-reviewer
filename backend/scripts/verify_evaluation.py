"""Test LLM evaluation on a few sample audit questions.

Runs the full RAG + LLM pipeline on 3 sample questions from the
APL 25-008 hospice questionnaire to verify evaluation quality
before processing the full set.

Usage:
    VOYAGE_API_KEY=key ANTHROPIC_API_KEY=key \
        uv run scripts/verify_evaluation.py data/processed
"""

import sys

from app.services.evaluator import Evaluator

SAMPLE_QUESTIONS = [
    {
        "number": 1,
        "text": (
            "Does the P&P state that under existing Contract requirements "
            "and state law, MCPs are required to provide hospice services "
            "upon Member election to start and receive such care services? "
            "Hospice coverage is provided in benefit periods: Two 90-day "
            "periods, beginning on the date of hospice election; followed "
            "by unlimited 60-day periods. A benefit period starts the day "
            "the Member receives hospice care and ends when the 90-day or "
            "60-day period ends."
        ),
    },
    {
        "number": 16,
        "text": (
            "Does the P&P state MCPs must not deny hospice care to Members "
            "certified as terminally ill?"
        ),
    },
    {
        "number": 43,
        "text": (
            "Does the P&P state MCPs cannot require authorization for room "
            "and board for Members receiving hospice services and residing "
            "in a skilled nursing facility (SNF)/NF or intermediate care "
            "facility (ICF) as described in federal law?"
        ),
    },
]


def main(processed_dir: str) -> None:
    """Run evaluation on sample questions and print results.

    Args:
        processed_dir: Path to directory containing the chroma/ folder.
    """
    chroma_path = f"{processed_dir}/chroma"
    evaluator = Evaluator(chroma_path=chroma_path)

    print(f"Model: {evaluator.model}")
    print(f"Chunks per question: {evaluator.n_results}\n")

    for q in SAMPLE_QUESTIONS:
        print(f"{'=' * 70}")
        print(f"Q{q['number']}: {q['text'][:90]}...")
        print(f"{'=' * 70}")

        result = evaluator.evaluate_question(q["text"])

        print(f"\n  Status: {result['status']}")
        print(f"  Citation: {result['citation']}")
        print(f"  Evidence: {result['evidence'][:200]}...")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: VOYAGE_API_KEY=key ANTHROPIC_API_KEY=key "
            "uv run scripts/verify_evaluation.py <processed_dir>"
        )
        sys.exit(1)

    main(sys.argv[1])
