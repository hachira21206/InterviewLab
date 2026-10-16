import pytest
import pytest_asyncio
import json
import httpx
from app.services.analysis_provider import GroqAnalysisProvider, AnalysisInput
from app.schemas.interview_evaluation import (
    InterviewEvaluationAISet,
    QuestionEvaluationAI,
)
from app.models.interview_evaluation import ReadinessLevel, EvaluationConfidence
from app.core.config import settings


@pytest_asyncio.fixture
def groq_provider(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "super_secret_groq_key_12345")
    monkeypatch.setattr(settings, "GROQ_MODEL", "llama-3.3-70b")
    monkeypatch.setattr(settings, "AI_REQUEST_TIMEOUT_SECONDS", 30)
    return GroqAnalysisProvider()


def valid_evaluation_payload():
    evals = []
    for i in range(1, 11):
        evals.append({
            "question_order": i,
            "technical_accuracy": 3.0,
            "completeness": 1.5,
            "reasoning_clarity": 1.5,
            "relevance": 1.0,
            "practical_example": 1.0,
            "total_score": 8.0,
            "feedback": f"Good answer for question {i}",
            "strengths": ["Clear", "Solid"],
            "missing_points": ["Could explain more"],
            "suggested_answer": f"Ideal answer for {i}",
            "study_topics": ["Backend", "Testing"],
            "confidence": "high"
        })
    return {
        "evaluations": evals,
        "overall_summary": "Very good candidate overall.",
        "key_strengths": ["Coding", "System design"],
        "knowledge_gaps": ["CI/CD pipelines"],
        "priority_improvements": ["Review unit tests"],
        "recommended_study_topics": ["Docker", "Kubernetes"],
        "short_term_study_plan": ["Week 1: Docker basics"],
        "next_interview_advice": "Prepare more live examples"
    }


@pytest.mark.asyncio
async def test_groq_evaluate_interview_success(groq_provider, monkeypatch):
    class MockResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {
                "choices": [{
                    "message": {
                        "content": json.dumps(valid_evaluation_payload())
                    }
                }],
                "usage": {"prompt_tokens": 150, "completion_tokens": 300}
            }

    async def mock_post(*args, **kwargs):
        assert kwargs["headers"]["Authorization"] == "Bearer super_secret_groq_key_12345"
        assert kwargs["json"]["response_format"]["type"] == "json_schema"
        assert kwargs["json"]["response_format"]["json_schema"]["strict"] is True
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    input_data = AnalysisInput("System instructions", "User prompt", InterviewEvaluationAISet.model_json_schema())
    result = await groq_provider.evaluate_interview(input_data)

    assert result.error_code is None
    assert result.data is not None
    assert len(result.data.evaluations) == 10
    assert result.input_tokens == 150
    assert result.output_tokens == 300


@pytest.mark.asyncio
async def test_groq_evaluate_interview_401(groq_provider, monkeypatch):
    class MockResponse:
        status_code = 401

    async def mock_post(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    input_data = AnalysisInput("Sys", "User", InterviewEvaluationAISet.model_json_schema())
    result = await groq_provider.evaluate_interview(input_data)

    assert result.error_code == "CONFIGURATION_ERROR"
    assert result.data is None


@pytest.mark.asyncio
async def test_groq_evaluate_interview_403(groq_provider, monkeypatch):
    class MockResponse:
        status_code = 403

    async def mock_post(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    input_data = AnalysisInput("Sys", "User", InterviewEvaluationAISet.model_json_schema())
    result = await groq_provider.evaluate_interview(input_data)

    assert result.error_code == "CONFIGURATION_ERROR"
    assert result.data is None


@pytest.mark.asyncio
async def test_groq_evaluate_interview_429(groq_provider, monkeypatch):
    class MockResponse:
        status_code = 429

    async def mock_post(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    input_data = AnalysisInput("Sys", "User", InterviewEvaluationAISet.model_json_schema())
    result = await groq_provider.evaluate_interview(input_data)

    assert result.error_code == "RATE_LIMITED"
    assert result.data is None


@pytest.mark.asyncio
async def test_groq_evaluate_interview_5xx(groq_provider, monkeypatch):
    class MockResponse:
        status_code = 503

    async def mock_post(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    input_data = AnalysisInput("Sys", "User", InterviewEvaluationAISet.model_json_schema())
    result = await groq_provider.evaluate_interview(input_data)

    assert result.error_code == "PROVIDER_UNAVAILABLE"
    assert result.data is None


@pytest.mark.asyncio
async def test_groq_evaluate_interview_timeout(groq_provider, monkeypatch):
    async def mock_post(*args, **kwargs):
        raise httpx.TimeoutException("Read timed out")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    input_data = AnalysisInput("Sys", "User", InterviewEvaluationAISet.model_json_schema())
    result = await groq_provider.evaluate_interview(input_data)

    assert result.error_code == "PROVIDER_TIMEOUT"
    assert result.data is None


@pytest.mark.asyncio
async def test_groq_evaluate_interview_network_error(groq_provider, monkeypatch):
    async def mock_post(*args, **kwargs):
        raise httpx.ConnectError("Connection refused to groq.com")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    input_data = AnalysisInput("Sys", "User", InterviewEvaluationAISet.model_json_schema())
    result = await groq_provider.evaluate_interview(input_data)

    assert result.error_code == "NETWORK_ERROR"
    assert result.data is None


@pytest.mark.asyncio
async def test_groq_evaluate_interview_empty_choices(groq_provider, monkeypatch):
    class MockResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"choices": []}

    async def mock_post(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    input_data = AnalysisInput("Sys", "User", InterviewEvaluationAISet.model_json_schema())
    result = await groq_provider.evaluate_interview(input_data)

    assert result.error_code == "INVALID_PROVIDER_RESPONSE"
    assert result.data is None


@pytest.mark.asyncio
async def test_groq_evaluate_interview_non_json(groq_provider, monkeypatch):
    class MockResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {
                "choices": [{
                    "message": {"content": "This is raw markdown, not JSON"}
                }]
            }

    async def mock_post(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    input_data = AnalysisInput("Sys", "User", InterviewEvaluationAISet.model_json_schema())
    result = await groq_provider.evaluate_interview(input_data)

    assert result.error_code == "INVALID_PROVIDER_RESPONSE"
    assert result.data is None


@pytest.mark.asyncio
async def test_groq_evaluate_interview_malformed_schema(groq_provider, monkeypatch):
    class MockResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {
                "choices": [{
                    "message": {
                        "content": json.dumps({"extra_invalid_key": "data"})
                    }
                }]
            }

    async def mock_post(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    input_data = AnalysisInput("Sys", "User", InterviewEvaluationAISet.model_json_schema())
    result = await groq_provider.evaluate_interview(input_data)

    assert result.error_code == "INVALID_PROVIDER_RESPONSE"
    assert result.data is None


@pytest.mark.asyncio
async def test_groq_evaluate_interview_refusal(groq_provider, monkeypatch):
    class MockResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {
                "choices": [{
                    "message": {
                        "refusal": "I cannot evaluate this content due to safety policy."
                    }
                }]
            }

    async def mock_post(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    input_data = AnalysisInput("Sys", "User", InterviewEvaluationAISet.model_json_schema())
    result = await groq_provider.evaluate_interview(input_data)

    assert result.error_code == "ANALYSIS_REFUSED"
    assert result.data is None


@pytest.mark.asyncio
async def test_groq_evaluate_interview_no_leak_api_key_or_traceback(groq_provider, monkeypatch):
    async def mock_post(*args, **kwargs):
        raise Exception(f"Internal socket crash with key: {settings.GROQ_API_KEY} at path /secret/db")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    input_data = AnalysisInput("Sys", "User", InterviewEvaluationAISet.model_json_schema())
    result = await groq_provider.evaluate_interview(input_data)

    assert result.error_code == "INTERNAL_ANALYSIS_ERROR"
    assert settings.GROQ_API_KEY not in (result.error_message or "")
    assert "/secret/db" not in (result.error_message or "")


@pytest.mark.asyncio
async def test_fake_analysis_provider_default_evaluation_success():
    from app.services.analysis_provider import FakeAnalysisProvider
    from app.services.interview_evaluation import compute_readiness_level

    fake = FakeAnalysisProvider()
    assert fake.mock_evaluation_result is None

    input_data = AnalysisInput("System instructions", "User prompt", InterviewEvaluationAISet.model_json_schema())
    result = await fake.evaluate_interview(input_data)

    assert result.error_code is None
    assert result.error_message is None
    assert result.data is not None

    # Assert 10 evaluations returned
    assert len(result.data.evaluations) == 10
    orders = [e.question_order for e in result.data.evaluations]
    assert orders == list(range(1, 11))

    # Assert AI response does NOT contain readiness_level (schema extra="forbid")
    dumped = result.data.model_dump()
    assert "readiness_level" not in dumped
    assert not hasattr(result.data, "readiness_level")

    # Readiness is computed only by backend service
    total_score = sum(e.total_score for e in result.data.evaluations)  # 80.0
    computed_readiness = compute_readiness_level(total_score)
    assert computed_readiness == ReadinessLevel.intern_ready
