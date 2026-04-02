"""Preprocess P&P documents into a ChromaDB collection for RAG retrieval.

Expects a root directory (e.g. data/policies) containing category subfolders
(AA, CMC, DD, GG, HH, etc.). For each PDF, extracts metadata from the header,
identifies PURPOSE, POLICY, and PROCEDURE sections using bold font detection
(TimesNewRomanPS-BoldMT at >10.5pt), and chunks at the lettered subsection
level (A., B., C., etc.). Chunks are stored in a ChromaDB persistent
collection with Voyage AI's voyage-law-2 embeddings.

Outputs:
    data/processed/chroma/  - ChromaDB persistent storage

Usage:
    uv run scripts/preprocess.py data/policies data/processed --dry-run
    uv run scripts/preprocess.py data/policies data/processed
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import chromadb
import pymupdf
from chromadb.utils import embedding_functions

REQUIRED_SECTIONS = {"PURPOSE", "POLICY", "PROCEDURE"}
SKIP_SECTIONS = {
    "ATTACHMENT(S)",
    "REFERENCE(S)",
    "REGULATORY AGENCY APPROVAL(S)",
    "BOARD ACTION(S)",
    "REVISION HISTORY",
    "GLOSSARY",
    "DEFINITIONS",
}
ALL_KNOWN_HEADERS = REQUIRED_SECTIONS | SKIP_SECTIONS
MIN_FONT_SIZE = 10.5


def extract_body_spans(page: pymupdf.Page, page_num: int) -> list[dict]:
    """Extract text spans from a page, filtering to body-size text only.

    Args:
        page: A PyMuPDF page object.
        page_num: Zero-indexed page number.

    Returns:
        A list of span dicts with keys: text, bold, page.
    """
    spans = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                if text and span["size"] > MIN_FONT_SIZE:
                    spans.append(
                        {
                            "text": text,
                            "bold": "Bold" in span["font"],
                            "page": page_num,
                        }
                    )
    return spans


def extract_metadata(doc: pymupdf.Document) -> dict:
    """Extract policy metadata from the first page header.

    Parses the standardized header block on page 1 to find the policy
    number, title, department, effective date, and revised date.

    Args:
        doc: An open PyMuPDF document.

    Returns:
        A dict with keys: policy_number, title, department, effective_date,
        revised_date.
    """
    spans = extract_body_spans(doc[0], 0)
    full_text = " ".join(s["text"] for s in spans)

    metadata = {
        "policy_number": _match_or_default(
            r"Policy:\s*([A-Z]{1,3}\.\d+\w*)", full_text
        ),
        "department": _match_or_default(
            r"Department:\s*(.+?)(?=Section:|CEO|$)", full_text
        ),
        "effective_date": _match_or_default(
            r"Effective Date:\s*(\d{2}/\d{2}/\d{4})", full_text
        ),
        "revised_date": _match_or_default(
            r"Revised Date:\s*(\d{2}/\d{2}/\d{4})", full_text
        ),
        "title": _extract_title(spans),
    }
    return metadata


def _match_or_default(pattern: str, text: str, default: str = "") -> str:
    """Return the first regex capture group match, or a default value.

    Args:
        pattern: Regex pattern with one capture group.
        text: Text to search.
        default: Value to return if no match is found.

    Returns:
        The matched group string, or the default.
    """
    match = re.search(pattern, text)
    return match.group(1).strip() if match else default


def _extract_title(spans: list[dict]) -> str:
    """Extract the document title from consecutive bold spans.

    Collects bold spans until a roman numeral section header is reached,
    skipping known section header names.

    Args:
        spans: List of span dicts from the first page.

    Returns:
        The concatenated title string.
    """
    parts = []
    for s in spans:
        if not s["bold"]:
            continue
        if s["text"] in ALL_KNOWN_HEADERS:
            continue
        if re.match(r"^[IVX]+\.$", s["text"]):
            break
        parts.append(s["text"])
    return " ".join(parts).strip()


def extract_chunks(pdf_path: str) -> list[dict]:
    """Extract text chunks from a P&P document at the subsection level.

    Identifies PURPOSE, POLICY, and PROCEDURE sections using bold font
    detection, then splits each section into chunks at the lettered
    subsection markers (A., B., C., etc.).

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        A list of chunk dicts with keys: section, subsection, page, text.
        Returns an empty list if required sections are not found.
    """
    doc = pymupdf.open(pdf_path)
    all_spans = []
    for page_num in range(len(doc)):
        all_spans.extend(extract_body_spans(doc[page_num], page_num))
    doc.close()

    return _build_chunks_from_spans(all_spans)


def _build_chunks_from_spans(spans: list[dict]) -> list[dict]:
    """Build subsection-level chunks from a flat list of text spans.

    Walks through spans tracking the current major section (PURPOSE, POLICY,
    PROCEDURE) and lettered subsection (A, B, C). Text is accumulated into
    the current chunk until a new subsection or section boundary is hit.

    Args:
        spans: Ordered list of span dicts with keys: text, bold, page.

    Returns:
        A list of chunk dicts with keys: section, subsection, page, text.
    """
    current_major = None
    current_sub = None
    chunks = []
    in_target = False

    for span in spans:
        if span["bold"] and span["text"] in ALL_KNOWN_HEADERS:
            current_major, current_sub, in_target = _handle_section_header(span["text"])
            continue

        if not in_target:
            continue

        if span["bold"] and re.match(r"^[IVX]+\.$", span["text"]):
            continue

        if re.match(r"^[A-Z]\.$", span["text"]):
            current_sub = span["text"][0]
            chunks.append(
                {
                    "section": current_major,
                    "subsection": current_sub,
                    "page": span["page"] + 1,
                    "text_parts": [],
                }
            )
            continue

        _append_span_to_chunks(chunks, current_major, current_sub, in_target, span)

    return _finalize_chunks(chunks)


def _handle_section_header(header: str) -> tuple[str | None, None, bool]:
    """Determine parser state when a section header is encountered.

    Args:
        header: The section header text.

    Returns:
        A tuple of (current_major, current_sub, in_target).
    """
    if header in REQUIRED_SECTIONS:
        return header, None, True
    return None, None, False


def _append_span_to_chunks(
    chunks: list[dict],
    current_major: str | None,
    current_sub: str | None,
    in_target: bool,
    span: dict,
) -> None:
    """Append a text span to the appropriate chunk.

    If a subsection chunk exists, appends to it. Otherwise, creates or
    appends to a section-level intro chunk.

    Args:
        chunks: The running list of chunks being built.
        current_major: Current major section name.
        current_sub: Current subsection letter.
        in_target: Whether we are inside a target section.
        span: The text span to append.
    """
    if chunks and current_sub:
        chunks[-1]["text_parts"].append(span["text"])
        return

    if not (current_major and in_target):
        return

    for c in chunks:
        if c["section"] == current_major and c["subsection"] == "_intro":
            c["text_parts"].append(span["text"])
            return

    chunks.append(
        {
            "section": current_major,
            "subsection": "_intro",
            "page": span["page"] + 1,
            "text_parts": [span["text"]],
        }
    )


def _finalize_chunks(chunks: list[dict]) -> list[dict]:
    """Join text parts and filter empty chunks.

    Args:
        chunks: Raw chunks with text_parts lists.

    Returns:
        Cleaned chunks with a single text string each.
    """
    result = []
    for chunk in chunks:
        text = " ".join(chunk["text_parts"]).strip()
        if text:
            result.append(
                {
                    "section": chunk["section"],
                    "subsection": chunk["subsection"],
                    "page": chunk["page"],
                    "text": text,
                }
            )
    return result


def extract_all_pdfs(policies_path: Path) -> tuple[list[dict], int]:
    """Walk the policies directory and extract chunks from all PDFs.

    Args:
        policies_path: Root directory containing policy folder codes.

    Returns:
        A tuple of (all_chunks, skipped_count).
    """
    all_chunks = []
    skipped = 0

    for pdf_file in sorted(policies_path.rglob("*.pdf")):
        folder_code = pdf_file.parent.name
        print(f"Processing [{folder_code}] {pdf_file.name}...")

        try:
            doc = pymupdf.open(str(pdf_file))
            metadata = extract_metadata(doc)
            doc.close()

            chunks = extract_chunks(str(pdf_file))
            if not chunks:
                print("  Skipped (no required sections found)")
                skipped += 1
                continue

            for chunk in chunks:
                chunk["policy_number"] = metadata["policy_number"]
                chunk["policy_title"] = metadata["title"]
                chunk["folder_code"] = folder_code
                chunk["source_file"] = pdf_file.name
            all_chunks.extend(chunks)
            print(f"  Extracted {len(chunks)} chunks")

        except Exception as e:
            print(f"  Error: {e}")
            skipped += 1

    return all_chunks, skipped


def print_extraction_stats(chunks: list[dict], skipped: int) -> None:
    """Print summary statistics about extracted chunks.

    Args:
        chunks: All extracted chunk dicts.
        skipped: Number of documents that were skipped.
    """
    total_words = sum(len(c["text"].split()) for c in chunks)
    approx_tokens = int(total_words * 1.3)

    print(f"\nTotal chunks: {len(chunks)}")
    print(f"Skipped: {skipped} documents")
    print(f"Total words: {total_words:,}")
    print(f"Approx tokens: {approx_tokens:,}")

    folder_counts: dict[str, int] = {}
    for c in chunks:
        folder_counts[c["folder_code"]] = folder_counts.get(c["folder_code"], 0) + 1
    print("\nChunks per folder:")
    for folder, count in sorted(folder_counts.items()):
        print(f"  {folder}: {count}")


def find_new_chunk_ids(
    collection: chromadb.Collection,
    chunk_ids: list[str],
) -> list[int]:
    """Identify which chunks are not yet stored in the collection.

    Args:
        collection: A ChromaDB collection.
        chunk_ids: Full list of chunk IDs to check.

    Returns:
        A list of indices into chunk_ids for chunks that need embedding.
    """
    existing_ids: set[str] = set()
    batch_size = 500
    for i in range(0, len(chunk_ids), batch_size):
        batch = chunk_ids[i : i + batch_size]
        result = collection.get(ids=batch)
        existing_ids.update(result["ids"])

    new_indices = [i for i, cid in enumerate(chunk_ids) if cid not in existing_ids]

    if existing_ids:
        stored = len(existing_ids)
        new = len(new_indices)
        print(f"\n{stored} chunks already stored, {new} new to embed.")
    else:
        print(f"\n{len(new_indices)} chunks to embed.")

    return new_indices


def store_chunks(
    all_chunks: list[dict],
    chunk_ids: list[str],
    new_indices: list[int],
    collection: chromadb.Collection,
) -> None:
    """Embed and store new chunks in ChromaDB with retry logic.

    Processes chunks in batches. On rate limit errors, waits with
    increasing backoff. On other errors, retries up to 3 times then
    exits gracefully so the script can be re-run to resume.

    Args:
        all_chunks: Full list of chunk dicts.
        chunk_ids: Full list of chunk IDs aligned with all_chunks.
        new_indices: Indices of chunks that need embedding.
        collection: A ChromaDB collection with an embedding function.
    """
    batch_size = 64
    total_batches = (len(new_indices) + batch_size - 1) // batch_size
    max_retries = 3

    for batch_num, start in enumerate(range(0, len(new_indices), batch_size), 1):
        batch_indices = new_indices[start : start + batch_size]
        batch_ids = [chunk_ids[i] for i in batch_indices]
        batch_docs = [all_chunks[i]["text"] for i in batch_indices]
        batch_meta = [
            {
                "policy_number": all_chunks[i]["policy_number"],
                "policy_title": all_chunks[i]["policy_title"],
                "folder_code": all_chunks[i]["folder_code"],
                "source_file": all_chunks[i]["source_file"],
                "section": all_chunks[i]["section"],
                "subsection": all_chunks[i]["subsection"],
                "page": all_chunks[i]["page"],
            }
            for i in batch_indices
        ]

        _upsert_batch_with_retry(
            collection,
            batch_ids,
            batch_docs,
            batch_meta,
            batch_num,
            total_batches,
            max_retries,
        )


def _upsert_batch_with_retry(  # noqa: PLR0913
    collection: chromadb.Collection,
    ids: list[str],
    documents: list[str],
    metadata: list[dict],
    batch_num: int,
    total_batches: int,
    max_retries: int,
) -> None:
    """Upsert a single batch into ChromaDB with retry on failure.

    Args:
        collection: A ChromaDB collection.
        ids: Chunk IDs for the batch.
        documents: Chunk texts for the batch.
        metadata: Chunk metadata dicts for the batch.
        batch_num: Current batch number for logging.
        total_batches: Total number of batches for logging.
        max_retries: Maximum number of retry attempts.
    """
    for attempt in range(1, max_retries + 1):
        try:
            print(f"  Batch {batch_num}/{total_batches} ({len(ids)} chunks)...")
            collection.upsert(ids=ids, documents=documents, metadatas=metadata)
            return
        except Exception as e:
            error_msg = str(e)
            is_rate_limit = "429" in error_msg or "RateLimit" in error_msg
            wait = 30 * attempt if is_rate_limit else 5

            if is_rate_limit:
                print(
                    f"    Rate limited. Waiting {wait}s"
                    f" (attempt {attempt}/{max_retries})..."
                )
            else:
                print(f"    Error: {e} (attempt {attempt}/{max_retries})")

            if attempt == max_retries:
                print(f"\n    Failed after {max_retries} attempts. Re-run to resume.")
                print(f"    {collection.count()} chunks stored so far.")
                sys.exit(1)

            time.sleep(wait)


def preprocess(policies_dir: str, output_dir: str, dry_run: bool = False) -> None:
    """Run the full preprocessing pipeline.

    Walks the policies directory, extracts chunks from each PDF. In dry-run
    mode, saves chunks as JSON and prints stats. Otherwise, stores chunks
    in a ChromaDB persistent collection with Voyage AI embeddings.

    Args:
        policies_dir: Root directory containing policy folder codes.
        output_dir: Directory to save processed output.
        dry_run: If True, extract and report stats only (no embedding).
    """
    policies_path = Path(policies_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not policies_path.exists():
        print(f"Directory not found: {policies_dir}")
        sys.exit(1)

    all_chunks, skipped = extract_all_pdfs(policies_path)
    print_extraction_stats(all_chunks, skipped)

    if dry_run:
        chunks_path = output_path / "chunks_preview.json"
        with chunks_path.open("w") as f:
            json.dump(all_chunks, f, indent=2)
        print(f"\nSaved preview to {chunks_path}")
        print("Dry run complete. Inspect chunks before running without --dry-run.")
        return

    voyage_key = os.environ.get("VOYAGE_API_KEY")
    if not voyage_key:
        print("Error: VOYAGE_API_KEY environment variable not set.")
        sys.exit(1)

    voyage_ef = embedding_functions.VoyageAIEmbeddingFunction(
        api_key=voyage_key,
        model_name="voyage-law-2",
    )

    chroma_path = str(output_path / "chroma")
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_or_create_collection(
        name="policy_chunks",
        embedding_function=voyage_ef,
    )

    chunk_ids = [
        f"{c['policy_number']}_{c['section']}_{c['subsection']}_{i}"
        for i, c in enumerate(all_chunks)
    ]

    new_indices = find_new_chunk_ids(collection, chunk_ids)
    if not new_indices:
        print(f"\nAll {len(all_chunks)} chunks already stored. Nothing to do.")
        return

    store_chunks(all_chunks, chunk_ids, new_indices, collection)
    print(f"\nStored {collection.count()} chunks in {chroma_path}")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--dry-run"]

    if len(args) < 2:
        print(
            "Usage: uv run scripts/preprocess.py"
            " <policies_dir> <output_dir> [--dry-run]"
        )
        sys.exit(1)

    preprocess(args[0], args[1], dry_run=dry_run)
