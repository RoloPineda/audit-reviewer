"""Tests for the FastAPI endpoints."""

import base64
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.main as main_mod
from app.main import app

AUTH_HEADER = {
    "Authorization": "Basic " + base64.b64encode(b"testuser:testpass").decode()
}


@pytest.fixture(autouse=True)
def _reset_evaluator():
    """Reset the global evaluator singleton between tests."""
    main_mod.evaluator = None
    yield
    main_mod.evaluator = None


@pytest.fixture(autouse=True)
def _set_auth_env(monkeypatch):
    """Configure auth credentials for all tests."""
    monkeypatch.setattr(main_mod, "AUTH_USERNAME", "testuser")
    monkeypatch.setattr(main_mod, "AUTH_PASSWORD", "testpass")


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthCheck:
    def test_returns_status(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert "status" in resp.json()


class TestQuestionnaireUpload:
    @patch("app.main.extract_questions")
    def test_rejects_non_pdf(self, mock_extract, client):
        resp = client.post(
            "/api/questionnaire",
            headers=AUTH_HEADER,
            files={"file": ("test.txt", b"not a pdf", "text/plain")},
        )
        assert resp.status_code == 400
        assert "PDF" in resp.json()["detail"]
        mock_extract.assert_not_called()

    @patch("app.main.extract_questions")
    def test_returns_422_when_no_questions_found(
        self, mock_extract, client
    ):
        mock_extract.return_value = {
            "metadata": {"apl_reference": "APL 25-008"},
            "questions": [],
        }
        resp = client.post(
            "/api/questionnaire",
            headers=AUTH_HEADER,
            files={
                "file": ("test.pdf", b"%PDF-fake", "application/pdf")
            },
        )
        assert resp.status_code == 422
        assert "No audit questions" in resp.json()["detail"]

    @patch("app.main.extract_questions")
    def test_returns_questions_on_success(self, mock_extract, client):
        mock_extract.return_value = {
            "metadata": {"apl_reference": "APL 25-008"},
            "questions": [
                {
                    "number": 1,
                    "text": "Does it comply?",
                    "reference": "APL 25-008, page 1",
                },
            ],
        }
        resp = client.post(
            "/api/questionnaire",
            headers=AUTH_HEADER,
            files={
                "file": ("audit.pdf", b"%PDF-fake", "application/pdf")
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["metadata"]["apl_reference"] == "APL 25-008"
        assert len(body["questions"]) == 1

    def test_rejects_unauthenticated_request(self, client):
        resp = client.post(
            "/api/questionnaire",
            files={
                "file": ("test.pdf", b"%PDF-fake", "application/pdf")
            },
        )
        assert resp.status_code == 401


class TestEvaluateEndpoint:
    @patch("app.main.get_evaluator")
    def test_returns_evaluation(self, mock_get_eval, client):
        mock_evaluator = MagicMock()
        mock_evaluator.evaluate_question.return_value = {
            "status": "met",
            "evidence": "Policy states X.",
            "citation": "AA.1001, POLICY.A, page 2",
            "chunks_used": [],
        }
        mock_get_eval.return_value = mock_evaluator

        resp = client.post(
            "/api/evaluate",
            headers=AUTH_HEADER,
            json={"question": "Does the P&P state something?"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "met"
        assert body["evidence"] == "Policy states X."
        assert body["citation"] == "AA.1001, POLICY.A, page 2"

    @patch("app.main.get_evaluator")
    def test_returns_error_status_on_evaluation_failure(
        self, mock_get_eval, client
    ):
        mock_evaluator = MagicMock()
        mock_evaluator.evaluate_question.return_value = {
            "status": "error",
            "evidence": "LLM returned garbage",
            "citation": "",
            "chunks_used": [],
        }
        mock_get_eval.return_value = mock_evaluator

        resp = client.post(
            "/api/evaluate",
            headers=AUTH_HEADER,
            json={"question": "Some question?"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"

    def test_rejects_missing_question_field(self, client):
        resp = client.post(
            "/api/evaluate",
            headers=AUTH_HEADER,
            json={},
        )
        assert resp.status_code == 422

    def test_rejects_unauthenticated_request(self, client):
        resp = client.post(
            "/api/evaluate",
            json={"question": "Something?"},
        )
        assert resp.status_code == 401
