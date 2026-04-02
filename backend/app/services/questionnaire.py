"""Extract structured audit questions from DHCS questionnaire PDFs.

Parses the standardized DHCS Submission Review Form format, extracting
header metadata (APL reference, title) and individual review questions
with their reference citations.

The expected format has a header section containing "SUBMISSION ITEM:"
followed by numbered questions in the form:
    N. Does the P&P state...
    (Reference: APL XX-XXX, page N)
    Yes  No
    Citation:

We extract:
    - Question text: the input to the RAG pipeline. Each question becomes a
      query we embed and search against policy chunks to find evidence.
    - Question number: for ordering and display in the results UI.
    - Reference: the APL page citation (e.g. "APL 25-008, page 2") that tells
      the auditor where in the regulation the requirement comes from.
    - Metadata: identifies which APL this questionnaire audits against, used
      for the UI header and potentially for filtering chunks by relevance.

Usage:
    from app.services.questionnaire import extract_questions

    result = extract_questions("path/to/questionnaire.pdf")
    result["metadata"]   # {"submission_item": "...", "apl_reference": "APL 25-008"}
    result["questions"]  # [{"number": 1, "text": "...", "reference": "..."}, ...]
"""

import re

import pymupdf

# Splits text at question boundaries ("N. Does ...") without consuming the match.
# Negative lookbehind prevents splitting mid-number (e.g. "0" inside "10. Does")
QUESTION_SPLIT_PATTERN = re.compile(r"(?=(?<!\d)\d{1,3}\.\s*Does\s)")

# Captures the APL reference inside parentheses at the end of a line,
# e.g. "(Reference: APL 25-008, page 2)"
REFERENCE_PATTERN = re.compile(r"\(Reference:\s*(.+?)\)\s*$", re.MULTILINE)

# Captures the APL title after "SUBMISSION ITEM:" in the form header,
# e.g. "Policy and Procedure (P&P) regarding All Plan Letter (APL) 25-008: ..."
# Stops at the "☐ APPROVED/DENIED" checkboxes that follow
SUBMISSION_ITEM_PATTERN = re.compile(
    r"SUBMISSION\s*ITEM:\s*(.+?)(?=☐|APPROVED|$)", re.DOTALL
)

# Strips the Yes/No answer options and Citation field that appear after each
# question's text. Used as a fallback to isolate the question body when no
# "(Reference: ...)" line is found
TRAILING_NOISE_PATTERN = re.compile(r"\s*(Yes|No|Citation:).*$", re.DOTALL)


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract raw text from all pages of a PDF.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Concatenated text from all pages.
    """
    doc = pymupdf.open(pdf_path)
    text = "".join(page.get_text() for page in doc)
    doc.close()
    return text


def extract_questionnaire_metadata(text: str) -> dict:
    """Extract header metadata from the questionnaire text.

    Pulls the APL number and submission title from the form header.
    These identify which regulation is being audited and are used
    in the UI header.

    Args:
        text: Raw text from the questionnaire PDF.

    Returns:
        A dict with keys: submission_item, apl_reference.
    """
    metadata = {"submission_item": "", "apl_reference": ""}

    match = SUBMISSION_ITEM_PATTERN.search(text)
    if match:
        raw = match.group(1).replace("\n", " ").strip()
        metadata["submission_item"] = re.sub(r"\s+", " ", raw)

    apl_match = re.search(r"APL\s+(\d{2}-\d{3})", text)
    if apl_match:
        metadata["apl_reference"] = apl_match.group(0)

    return metadata


def clean_question_text(text: str) -> str:
    """Normalize whitespace in extracted question text.

    PyMuPDF inserts newlines at line breaks in the PDF layout.
    This collapses them into single spaces for clean display
    and embedding.

    Args:
        text: Raw question text with PDF line breaks.

    Returns:
        Cleaned question text as a single line.
    """
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_single_question(raw_block: str) -> dict | None:
    """Parse a single question block into structured fields.

    Extracts the question number (for display ordering), the question
    text (used as the RAG query), and the APL reference (shown in
    the audit report alongside the evidence).

    Args:
        raw_block: Raw text of one question block.

    Returns:
        A dict with keys: number, text, reference. Returns None if the
        block cannot be parsed.
    """
    number_match = re.match(r"(\d{1,3})\.\s*", raw_block)
    if not number_match:
        return None

    number = int(number_match.group(1))
    body = raw_block[number_match.end() :]

    ref_match = REFERENCE_PATTERN.search(body)
    reference = ref_match.group(1).strip() if ref_match else ""

    if ref_match:
        question_text = body[: ref_match.start()]
    else:
        question_text = TRAILING_NOISE_PATTERN.sub("", body)

    question_text = clean_question_text(question_text)

    if not question_text:
        return None

    return {
        "number": number,
        "text": question_text,
        "reference": reference,
    }


def extract_questions(pdf_path: str) -> dict:
    """Extract all audit questions from a questionnaire PDF.

    Returns the questionnaire metadata and a list of structured questions
    parsed from the DHCS Submission Review Form.

    Args:
        pdf_path: Path to the questionnaire PDF.

    Returns:
        A dict with keys: metadata (dict), questions (list of dicts).
        Each question dict has keys: number, text, reference.
    """
    text = extract_text_from_pdf(pdf_path)
    metadata = extract_questionnaire_metadata(text)

    questions_start = re.search(r"1\.\s*Does\s", text)
    if not questions_start:
        return {"metadata": metadata, "questions": []}

    questions_text = text[questions_start.start() :]
    raw_blocks = QUESTION_SPLIT_PATTERN.split(questions_text)
    raw_blocks = [b for b in raw_blocks if b.strip()]

    questions = []
    for block in raw_blocks:
        parsed = parse_single_question(block)
        if parsed:
            questions.append(parsed)

    return {"metadata": metadata, "questions": questions}
