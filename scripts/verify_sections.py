"""Verify that all P&P documents contain Purpose, Policy, and Procedure sections.

Expects a root directory (e.g. data/policies_procedures) containing category subfolders
(AA, CMC, DD, GG, HH, etc.). Recursively finds all PDFs within those
subfolders, opens each one, and checks for the presence of bold font spans
(e.g. TimesNewRomanPS-BoldMT) at body text size (>10.5pt) matching the
section header names PURPOSE, POLICY, and PROCEDURE. Reports any documents
missing one or more of these required sections.

Results: 369/373 documents have all required sections

Documents missing sections (4):
  [AA] AA.1000_CEO20250206_v20250201.pdf
    Missing: POLICY, PROCEDURE

  [GG] GG.1110_CEO20241031_v20241001.pdf
    Missing: PROCEDURE

  [MA] MA.1001_v20240101_CEO20240129_no attachments.pdf
    Missing: POLICY, PROCEDURE

  [PA] PA.1000_CEO20240924_v20240901.pdf
    Missing: POLICY, PROCEDURE
Usage:
    uv run scripts/verify_sections.py data/policies_procedures
"""

import sys
from pathlib import Path

import pymupdf

REQUIRED_SECTIONS = {"PURPOSE", "POLICY", "PROCEDURE"}


def find_bold_headers(pdf_path: str) -> set[str]:
    """Extract bold header text from a PDF using font attributes.

    Looks for spans using a bold font at body text size (>10.5pt)
    that match known section header names.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        A set of header names found in the document.
    """
    doc = pymupdf.open(pdf_path)
    headers = set()

    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    is_bold = "Bold" in span["font"]
                    is_body_size = span["size"] > 10.5

                    if is_bold and is_body_size and text in REQUIRED_SECTIONS:
                        headers.add(text)

    doc.close()
    return headers


def verify_policies(policies_dir: str) -> None:
    """Walk the policies directory and verify each PDF has required sections.

    Args:
        policies_dir: Root directory containing policy folder codes (AA, GG, etc.).
    """
    policies_path = Path(policies_dir)
    if not policies_path.exists():
        print(f"Directory not found: {policies_dir}")
        sys.exit(1)

    total = 0
    passed = 0
    failed = []

    for pdf_file in sorted(policies_path.rglob("*.pdf")):
        total += 1
        folder_code = pdf_file.parent.name
        headers = find_bold_headers(str(pdf_file))
        missing = REQUIRED_SECTIONS - headers

        if missing:
            failed.append((folder_code, pdf_file.name, missing))
        else:
            passed += 1

    print(f"\nResults: {passed}/{total} documents have all required sections\n")

    if failed:
        print(f"Documents missing sections ({len(failed)}):\n")
        for folder_code, filename, missing in failed:
            missing_str = ", ".join(sorted(missing))
            print(f"  [{folder_code}] {filename}")
            print(f"    Missing: {missing_str}\n")
    else:
        print("All documents passed.")


if __name__ == "__main__":
    policies_dir = sys.argv[1] if len(sys.argv) > 1 else "data/policies"
    verify_policies(policies_dir)