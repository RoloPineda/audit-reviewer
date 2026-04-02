"""Search extracted chunks by keyword for spot-checking retrieval gaps.

Loads chunks_preview.json and finds chunks containing all specified
keywords (case-insensitive). Useful for verifying whether specific
policy language exists in the corpus when the vector search misses it.

Usage:
    uv run scripts/search_chunks.py data/processed/chunks_preview.json "deny" "hospice"
    uv run scripts/search_chunks.py data/processed/chunks_preview.json "authorization" "room and board"
"""

import json
import sys
from pathlib import Path


def search_chunks(chunks_path: str, keywords: list[str]) -> None:
    """Search chunks for entries containing all specified keywords.

    Args:
        chunks_path: Path to chunks_preview.json.
        keywords: List of keywords that must all appear (case-insensitive).
    """
    with Path(chunks_path).open() as f:
        chunks = json.load(f)

    keywords_lower = [k.lower() for k in keywords]
    matches = [
        c for c in chunks
        if all(k in c["text"].lower() for k in keywords_lower)
    ]

    print(f"Searching for: {keywords}")
    print(f"Found: {len(matches)} chunks\n")

    for c in matches:
        print(f"[{c['policy_number']} {c['section']}.{c['subsection']} p{c['page']}]")
        print(f"  {c['policy_title']}")
        print(f"  {c['text'][:200]}...")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            "Usage: uv run scripts/search_chunks.py "
            "<chunks_json> <keyword1> [keyword2] ..."
        )
        sys.exit(1)

    search_chunks(sys.argv[1], sys.argv[2:])