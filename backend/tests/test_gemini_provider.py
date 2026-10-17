import json

import httpx
import pytest

from app.core.config import settings
from app.schemas.application_analysis import CandidateAnalysis
from app.services.analysis_provider import AnalysisInput, GeminiAnalysisProvider


def _candidate_analysis_json() -> str:
    return json.dumps(
        {
            "summary_vi": "Ứng viên có nền tảng phù hợp để luyện phỏng vấn Intern.",
            "candidate_level": "beginner",
            "technical_skills": [],
            "projects": [],
            "education": [],
            "strengths": [],
            "gaps": [],
            "matched_requirements": [],
            "missing_requirements": [],
            "recommended_interview_topics": [],
            "language_detected": "vi",
            "warnings": [],
        }
    )


@pytest.mark.asyncio
async def test_gemini_retries_complex_schema_in_json_mode(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test_gemini_key")
    monkeypatch.setattr(settings, "GEMINI_MODEL", "test-model")
    monkeypatch.setattr(settings, "GEMINI_BASE_URL", "https://example.test/v1beta")
    monkeypatch.setattr(settings, "AI_REQUEST_TIMEOUT_SECONDS", 30)
    GeminiAnalysisProvider._native_schema_available = True

    payloads = []

    class MockResponse:
        def __init__(self, status_code: int, data: dict):
            self.status_code = status_code
            self._data = data

        def raise_for_status(self):
            return None

        def json(self):
            return self._data

    async def mock_post(*args, **kwargs):
        payloads.append(kwargs["json"])
        if len(payloads) == 1:
            return MockResponse(400, {"error": {"message": "Invalid schema"}})
        return MockResponse(
            200,
            {
                "candidates": [
                    {"content": {"parts": [{"text": _candidate_analysis_json()}]}}
                ],
                "usageMetadata": {
                    "promptTokenCount": 25,
                    "candidatesTokenCount": 15,
                },
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    try:
        provider = GeminiAnalysisProvider()
        result = await provider.analyze_application(
            AnalysisInput("System prompt", "User data", CandidateAnalysis.model_json_schema())
        )

        assert result.error_code is None
        assert result.data is not None
        assert result.input_tokens == 25
        assert result.output_tokens == 15
        assert len(payloads) == 2
        assert "responseJsonSchema" in payloads[0]["generationConfig"]
        assert "responseJsonSchema" not in payloads[1]["generationConfig"]
        fallback_instruction = payloads[1]["systemInstruction"]["parts"][0]["text"]
        assert "JSON Schema" in fallback_instruction
        assert "summary_vi" in fallback_instruction
        assert "User data" not in fallback_instruction
        assert GeminiAnalysisProvider._native_schema_available is False
    finally:
        GeminiAnalysisProvider._native_schema_available = True
