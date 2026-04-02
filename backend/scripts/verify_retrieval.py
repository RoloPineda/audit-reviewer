"""Test retrieval quality by querying ChromaDB with sample audit questions.

Loads the pre-embedded policy chunks collection and queries it with
a few questions from the APL 25-008 hospice questionnaire. Displays
the top-k results for each question so retrieval quality can be
visually inspected before wiring up the LLM evaluation.

Usage:
    VOYAGE_API_KEY=your_key uv run scripts/verify_retrieval.py data/processed
"""

import os
import sys
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

SAMPLE_QUESTIONS = [
    {
        "number": 1,
        "text": (
            "Does the P&P state that under existing Contract requirements "
            "and state law, MCPs are required to provide hospice services "
            "upon Member election to start and receive such care services?"
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


def test_retrieval(processed_dir: str, n_results: int = 7) -> None:
    """Query ChromaDB with sample questions and display results.

    Args:
        processed_dir: Path to the directory containing the chroma/ folder.
        n_results: Number of chunks to retrieve per question.
    """
    voyage_key = os.environ.get("VOYAGE_API_KEY")
    if not voyage_key:
        print("Error: VOYAGE_API_KEY environment variable not set.")
        sys.exit(1)

    voyage_ef = embedding_functions.VoyageAIEmbeddingFunction(
        api_key=voyage_key,
        model_name="voyage-law-2",
    )

    chroma_path = str(Path(processed_dir) / "chroma")
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_collection(
        name="policy_chunks",
        embedding_function=voyage_ef,
    )

    print(f"Collection: {collection.count()} chunks\n")

    for question in SAMPLE_QUESTIONS:
        print(f"{'=' * 70}")
        print(f"Q{question['number']}: {question['text'][:100]}...")
        print(f"{'=' * 70}")

        results = collection.query(
            query_texts=[question["text"]],
            n_results=n_results,
        )

        for i in range(len(results["ids"][0])):
            meta = results["metadata"][0][i]
            doc = results["documents"][0][i]
            distance = results["distances"][0][i]
            preview = doc[:150].replace("\n", " ")

            print(f"\n  [{i + 1}] {meta['policy_number']} "
                  f"{meta['section']}.{meta['subsection']} "
                  f"(p{meta['page']}) "
                  f"dist={distance:.4f}")
            print(f"      {meta['policy_title'][:60]}")
            print(f"      {preview}...")

        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: VOYAGE_API_KEY=key"
            " uv run scripts/verify_retrieval.py <processed_dir>"
        )
        sys.exit(1)

    test_retrieval(sys.argv[1])
