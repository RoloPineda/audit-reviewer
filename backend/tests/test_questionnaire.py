"""Tests for the questionnaire extraction service.

Validates extraction against the APL 25-008 hospice audit questionnaire
located at backend/data/questionnaire/.
"""

from pathlib import Path

import pytest

from app.services.questionnaire import (
    clean_question_text,
    extract_questions,
    extract_questionnaire_metadata,
    extract_text_from_pdf,
    parse_single_question,
)

DATA_DIR = Path(__file__).parent.parent / "data" / "questionnaire"
QUESTIONNAIRE_PDF = DATA_DIR / "audit_questions.pdf"


@pytest.fixture
def raw_text():
    """Extract raw text from the questionnaire PDF."""
    return extract_text_from_pdf(str(QUESTIONNAIRE_PDF))


@pytest.fixture
def result():
    """Extract structured questions from the questionnaire PDF."""
    return extract_questions(str(QUESTIONNAIRE_PDF))


class TestExtractQuestionnaireMetadata:
    """Tests for header metadata extraction."""

    def test_extracts_apl_reference(self, raw_text):
        metadata = extract_questionnaire_metadata(raw_text)
        assert metadata["apl_reference"] == "APL 25-008"

    def test_extracts_submission_item(self, raw_text):
        metadata = extract_questionnaire_metadata(raw_text)
        assert "Hospice" in metadata["submission_item"]
        assert "APL" in metadata["submission_item"]


class TestCleanQuestionText:
    """Tests for question text cleaning."""

    def test_collapses_newlines(self):
        text = "Does the P&P state\nthat MCPs are required\nto provide services?"
        assert "\n" not in clean_question_text(text)

    def test_collapses_multiple_spaces(self):
        text = "Does the  P&P   state that MCPs are required?"
        assert "  " not in clean_question_text(text)

    def test_strips_whitespace(self):
        text = "  Does the P&P state something?  "
        assert clean_question_text(text) == "Does the P&P state something?"


class TestParseSingleQuestion:
    """Tests for individual question block parsing."""

    def test_parses_simple_question(self):
        block = (
            "1. Does the P&P state that MCPs must provide hospice?\n"
            "(Reference: APL 25-008, page 1)\n"
            " Yes     No\nCitation:"
        )
        parsed = parse_single_question(block)
        assert parsed["number"] == 1
        assert parsed["text"].startswith("Does the P&P state")
        assert parsed["reference"] == "APL 25-008, page 1"

    def test_parses_multi_digit_number(self):
        block = (
            "42. Does the P&P state something important?\n"
            "(Reference: APL 25-008, page 12)\n"
            " Yes     No\nCitation:"
        )
        parsed = parse_single_question(block)
        assert parsed["number"] == 42

    def test_returns_none_for_invalid_block(self):
        assert parse_single_question("not a question") is None

    def test_returns_none_for_empty_text(self):
        assert parse_single_question("1. \n(Reference: APL 25-008, page 1)") is None


class TestExtractQuestions:
    """Tests for full questionnaire extraction against APL 25-008."""

    def test_extracts_all_64_questions(self, result):
        assert len(result["questions"]) == 64

    def test_questions_are_sequentially_numbered(self, result):
        numbers = [q["number"] for q in result["questions"]]
        assert numbers == list(range(1, 65))

    def test_all_questions_have_text(self, result):
        for q in result["questions"]:
            assert len(q["text"]) > 0

    def test_all_questions_have_references(self, result):
        for q in result["questions"]:
            assert q["reference"].startswith("APL 25-008")

    def test_first_question_mentions_hospice(self, result):
        q1 = result["questions"][0]
        assert "hospice" in q1["text"].lower()

    def test_last_question_mentions_audit(self, result):
        q64 = result["questions"][-1]
        assert "inspect" in q64["text"].lower() or "audit" in q64["text"].lower()

    def test_metadata_present(self, result):
        assert result["metadata"]["apl_reference"] == "APL 25-008"
        assert len(result["metadata"]["submission_item"]) > 0

    def test_no_form_elements_in_question_text(self, result):
        for q in result["questions"]:
            assert "Citation:" not in q["text"]
            assert "\nYes" not in q["text"]
            assert "\nNo" not in q["text"]