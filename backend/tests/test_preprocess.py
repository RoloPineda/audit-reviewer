"""Tests for the preprocessing pipeline's pure logic functions."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.preprocess import (
    _build_chunks_from_spans,
    _extract_title,
    _finalize_chunks,
    _handle_section_header,
    _match_or_default,
)


def _span(text: str, bold: bool = False, page: int = 0) -> dict:
    """Create a minimal span dict for testing."""
    return {"text": text, "bold": bold, "page": page}


class TestMatchOrDefault:
    def test_returns_captured_group_on_match(self):
        result = _match_or_default(r"Policy:\s*([A-Z]+\.\d+)", "Policy: AA.1001")
        assert result == "AA.1001"

    def test_returns_default_on_no_match(self):
        result = _match_or_default(r"Policy:\s*([A-Z]+\.\d+)", "no match here")
        assert result == ""

    def test_returns_custom_default(self):
        result = _match_or_default(r"nope", "text", default="N/A")
        assert result == "N/A"

    def test_strips_whitespace_from_match(self):
        text = "Dept: Legal Section:"
        result = _match_or_default(r"Dept:\s*(.+?)(?=Section:)", text)
        assert result == "Legal"


class TestExtractTitle:
    def test_collects_bold_spans(self):
        spans = [
            _span("Code of", bold=True),
            _span("Conduct", bold=True),
        ]
        assert _extract_title(spans) == "Code of Conduct"

    def test_skips_non_bold_spans(self):
        spans = [
            _span("Code of", bold=True),
            _span("some body text", bold=False),
            _span("Conduct", bold=True),
        ]
        assert _extract_title(spans) == "Code of Conduct"

    def test_skips_known_section_headers(self):
        spans = [
            _span("My Policy Title", bold=True),
            _span("PURPOSE", bold=True),
        ]
        assert _extract_title(spans) == "My Policy Title"

    def test_stops_at_roman_numeral(self):
        spans = [
            _span("Title Part", bold=True),
            _span("I.", bold=True),
            _span("More Bold Text", bold=True),
        ]
        assert _extract_title(spans) == "Title Part"

    def test_returns_empty_string_when_no_bold(self):
        spans = [_span("plain text", bold=False)]
        assert _extract_title(spans) == ""


class TestHandleSectionHeader:
    def test_required_section_activates_target(self):
        assert _handle_section_header("PURPOSE") == ("PURPOSE", None, True)
        assert _handle_section_header("POLICY") == ("POLICY", None, True)
        assert _handle_section_header("PROCEDURE") == (
            "PROCEDURE",
            None,
            True,
        )

    def test_skip_section_deactivates_target(self):
        assert _handle_section_header("ATTACHMENT(S)") == (
            None,
            None,
            False,
        )
        assert _handle_section_header("REVISION HISTORY") == (
            None,
            None,
            False,
        )


class TestFinalizeChunks:
    def test_joins_text_parts(self):
        chunks = [
            {
                "section": "POLICY",
                "subsection": "A",
                "page": 1,
                "text_parts": ["hello", "world"],
            },
        ]
        result = _finalize_chunks(chunks)
        assert len(result) == 1
        assert result[0]["text"] == "hello world"
        assert "text_parts" not in result[0]

    def test_drops_empty_chunks(self):
        chunks = [
            {
                "section": "POLICY",
                "subsection": "A",
                "page": 1,
                "text_parts": [""],
            },
            {
                "section": "POLICY",
                "subsection": "B",
                "page": 2,
                "text_parts": ["content"],
            },
        ]
        result = _finalize_chunks(chunks)
        assert len(result) == 1
        assert result[0]["subsection"] == "B"

    def test_empty_input(self):
        assert _finalize_chunks([]) == []


class TestBuildChunksFromSpans:
    def test_single_section_with_subsections(self):
        spans = [
            _span("PURPOSE", bold=True),
            _span("A.", page=0),
            _span("First subsection text.", page=0),
            _span("B.", page=1),
            _span("Second subsection text.", page=1),
        ]
        result = _build_chunks_from_spans(spans)
        assert len(result) == 2  # noqa: PLR2004
        assert result[0]["section"] == "PURPOSE"
        assert result[0]["subsection"] == "A"
        assert result[0]["text"] == "First subsection text."
        assert result[0]["page"] == 1
        assert result[1]["subsection"] == "B"
        assert result[1]["page"] == 2  # noqa: PLR2004

    def test_multiple_sections(self):
        spans = [
            _span("PURPOSE", bold=True),
            _span("A.", page=0),
            _span("Purpose text.", page=0),
            _span("POLICY", bold=True),
            _span("A.", page=1),
            _span("Policy text.", page=1),
        ]
        result = _build_chunks_from_spans(spans)
        assert len(result) == 2  # noqa: PLR2004
        assert result[0]["section"] == "PURPOSE"
        assert result[1]["section"] == "POLICY"

    def test_skip_section_stops_collection(self):
        spans = [
            _span("PURPOSE", bold=True),
            _span("A.", page=0),
            _span("Collected.", page=0),
            _span("ATTACHMENT(S)", bold=True),
            _span("A.", page=1),
            _span("Should not appear.", page=1),
        ]
        result = _build_chunks_from_spans(spans)
        assert len(result) == 1
        assert result[0]["section"] == "PURPOSE"

    def test_intro_text_before_first_subsection(self):
        spans = [
            _span("POLICY", bold=True),
            _span("Intro text before any letter.", page=0),
            _span("A.", page=0),
            _span("Subsection content.", page=0),
        ]
        result = _build_chunks_from_spans(spans)
        assert len(result) == 2  # noqa: PLR2004
        intro = next(
            c for c in result if c["subsection"] == "_intro"
        )
        assert intro["text"] == "Intro text before any letter."

    def test_roman_numerals_are_skipped(self):
        spans = [
            _span("PURPOSE", bold=True),
            _span("I.", bold=True),
            _span("A.", page=0),
            _span("Real content.", page=0),
        ]
        result = _build_chunks_from_spans(spans)
        assert len(result) == 1
        assert result[0]["text"] == "Real content."

    def test_text_outside_target_section_is_ignored(self):
        spans = [
            _span("Some stray text.", page=0),
            _span("PURPOSE", bold=True),
            _span("A.", page=0),
            _span("Captured.", page=0),
        ]
        result = _build_chunks_from_spans(spans)
        assert len(result) == 1
        assert result[0]["text"] == "Captured."

    def test_empty_spans(self):
        assert _build_chunks_from_spans([]) == []

    def test_section_with_no_text_produces_no_chunks(self):
        spans = [
            _span("PURPOSE", bold=True),
            _span("POLICY", bold=True),
            _span("A.", page=0),
            _span("Policy content.", page=0),
        ]
        result = _build_chunks_from_spans(spans)
        assert len(result) == 1
        assert result[0]["section"] == "POLICY"

    def test_multipage_subsection(self):
        spans = [
            _span("PROCEDURE", bold=True),
            _span("A.", page=2),
            _span("Start of text.", page=2),
            _span("Continued on next page.", page=3),
        ]
        result = _build_chunks_from_spans(spans)
        assert len(result) == 1
        assert result[0]["text"] == "Start of text. Continued on next page."
        assert result[0]["page"] == 3  # noqa: PLR2004
