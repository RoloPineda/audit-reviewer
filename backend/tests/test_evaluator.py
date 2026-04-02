"""Tests for the evaluator service's pure utility functions."""

import json

import pytest

from app.services.evaluator import _format_excerpts, _parse_llm_response


class TestParseLlmResponse:
    def test_parses_raw_json(self):
        raw = json.dumps({
            "status": "met",
            "evidence": "Policy states X.",
            "citation": "AA.1001, POLICY.A, page 2",
        })
        result = _parse_llm_response(raw)
        assert result["status"] == "met"
        assert result["evidence"] == "Policy states X."
        assert result["citation"] == "AA.1001, POLICY.A, page 2"

    def test_parses_json_fenced_with_language_tag(self):
        payload = '{"status": "not_met", "evidence": "Missing.", "citation": ""}'
        raw = f"```json\n{payload}\n```"
        result = _parse_llm_response(raw)
        assert result["status"] == "not_met"
        assert result["evidence"] == "Missing."

    def test_parses_json_fenced_without_language_tag(self):
        raw = '```\n{"status": "met", "evidence": "Found.", "citation": "X"}\n```'
        result = _parse_llm_response(raw)
        assert result["status"] == "met"

    def test_parses_json_with_surrounding_whitespace(self):
        raw = '  \n {"status": "met", "evidence": "E", "citation": "C"} \n '
        result = _parse_llm_response(raw)
        assert result["status"] == "met"

    def test_raises_on_invalid_json(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_llm_response("This is not JSON at all.")

    def test_raises_on_empty_string(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_llm_response("")

    def test_parses_partially_met_status(self):
        raw = json.dumps({
            "status": "partially_met",
            "evidence": "Some parts addressed.",
            "citation": "GG.1503, PROCEDURE.C, page 5",
        })
        result = _parse_llm_response(raw)
        assert result["status"] == "partially_met"

    def test_parses_fenced_json_with_trailing_text_after_fence(self):
        raw = (
            '```json\n'
            '{"status": "met", "evidence": "Found.", "citation": "X"}\n'
            '```\n'
            'Some trailing explanation the LLM added.'
        )
        result = _parse_llm_response(raw)
        assert result["status"] == "met"

    def test_preserves_multiline_evidence(self):
        payload = {
            "status": "met",
            "evidence": "Line one.\nLine two.\nLine three.",
            "citation": "AA.1000, PURPOSE.A, page 1",
        }
        raw = json.dumps(payload)
        result = _parse_llm_response(raw)
        assert result["evidence"] == "Line one.\nLine two.\nLine three."


class TestFormatExcerpts:
    def _make_results(self, entries: list[dict]) -> dict:
        """Build a ChromaDB-shaped results dict from simplified entries."""
        return {
            "ids": [[e["id"] for e in entries]],
            "documents": [[e["doc"] for e in entries]],
            "metadatas": [[e["meta"] for e in entries]],
        }

    def test_formats_single_excerpt(self):
        results = self._make_results([
            {
                "id": "chunk_0",
                "doc": "All members must receive hospice care.",
                "meta": {
                    "policy_number": "GG.1503",
                    "section": "POLICY",
                    "subsection": "A",
                    "page": 2,
                },
            },
        ])
        formatted = _format_excerpts(results)
        assert "[GG.1503, POLICY.A, page 2]" in formatted
        assert "All members must receive hospice care." in formatted

    def test_formats_multiple_excerpts_separated_by_blank_lines(self):
        results = self._make_results([
            {
                "id": "chunk_0",
                "doc": "First excerpt.",
                "meta": {
                    "policy_number": "AA.1001",
                    "section": "PURPOSE",
                    "subsection": "A",
                    "page": 1,
                },
            },
            {
                "id": "chunk_1",
                "doc": "Second excerpt.",
                "meta": {
                    "policy_number": "BB.2002",
                    "section": "PROCEDURE",
                    "subsection": "B",
                    "page": 3,
                },
            },
        ])
        formatted = _format_excerpts(results)
        assert "[AA.1001, PURPOSE.A, page 1]" in formatted
        assert "[BB.2002, PROCEDURE.B, page 3]" in formatted
        assert "\n\n" in formatted

    def test_handles_empty_results(self):
        results = {"ids": [[]], "documents": [[]], "metadatas": [[]]}
        formatted = _format_excerpts(results)
        assert formatted == ""

    def test_label_format_matches_citation_style(self):
        results = self._make_results([
            {
                "id": "chunk_0",
                "doc": "Text.",
                "meta": {
                    "policy_number": "HH.3000",
                    "section": "POLICY",
                    "subsection": "_intro",
                    "page": 10,
                },
            },
        ])
        formatted = _format_excerpts(results)
        lines = formatted.split("\n")
        assert lines[0] == "[HH.3000, POLICY._intro, page 10]"
        assert lines[1] == "Text."
