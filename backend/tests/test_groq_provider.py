import pytest
import pytest_asyncio
import json
import httpx
from pydantic import BaseModel
from app.services.analysis_provider import GroqAnalysisProvider, AnalysisInput
from app.core.config import settings

@pytest_asyncio.fixture
def groq_provider(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test_key")
    monkeypatch.setattr(settings, "GROQ_MODEL", "test_model")
    monkeypatch.setattr(settings, "AI_REQUEST_TIMEOUT_SECONDS", 30)
    return GroqAnalysisProvider()

@pytest.mark.asyncio
async def test_groq_success(groq_provider, monkeypatch):
    class MockResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "summary_vi": "Test summary",
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
                            "warnings": []
                        })
                    }
                }],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20}
            }

    async def mock_post(*args, **kwargs):
        assert kwargs["headers"]["Authorization"] == "Bearer test_key"
        assert kwargs["json"]["model"] == "test_model"
        assert "temperature" in kwargs["json"]
        assert kwargs["json"]["response_format"]["type"] == "json_schema"
        assert kwargs["json"]["response_format"]["json_schema"]["strict"] is True
        messages = kwargs["json"]["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    from app.schemas.application_analysis import CandidateAnalysis
    input_data = AnalysisInput("Sys", "User", CandidateAnalysis.model_json_schema())
    result = await groq_provider.analyze_application(input_data)
    
    assert result.error_code is None
    assert result.data is not None

@pytest.mark.asyncio
async def test_groq_401(groq_provider, monkeypatch):
    class MockResponse:
        status_code = 401
        def raise_for_status(self): pass
    async def mock_post(*args, **kwargs): return MockResponse()
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    res = await groq_provider.analyze_application(AnalysisInput("Sys", "User", {}))
    assert res.error_code == "CONFIGURATION_ERROR"

@pytest.mark.asyncio
async def test_groq_403(groq_provider, monkeypatch):
    class MockResponse:
        status_code = 403
        def raise_for_status(self): pass
    async def mock_post(*args, **kwargs): return MockResponse()
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    res = await groq_provider.analyze_application(AnalysisInput("Sys", "User", {}))
    assert res.error_code == "CONFIGURATION_ERROR"
    assert "test_key" not in (res.error_message or "")

@pytest.mark.asyncio
async def test_groq_429(groq_provider, monkeypatch):
    class MockResponse:
        status_code = 429
        def raise_for_status(self): pass
    async def mock_post(*args, **kwargs): return MockResponse()
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    res = await groq_provider.analyze_application(AnalysisInput("Sys", "User", {}))
    assert res.error_code == "RATE_LIMITED"

@pytest.mark.asyncio
async def test_groq_500(groq_provider, monkeypatch):
    class MockResponse:
        status_code = 500
        def raise_for_status(self): pass
    async def mock_post(*args, **kwargs): return MockResponse()
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    res = await groq_provider.analyze_application(AnalysisInput("Sys", "User", {}))
    assert res.error_code == "PROVIDER_UNAVAILABLE"

@pytest.mark.asyncio
async def test_groq_503(groq_provider, monkeypatch):
    class MockResponse:
        status_code = 503
        def raise_for_status(self): pass
    async def mock_post(*args, **kwargs): return MockResponse()
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    res = await groq_provider.analyze_application(AnalysisInput("Sys", "User", {}))
    assert res.error_code == "PROVIDER_UNAVAILABLE"

@pytest.mark.asyncio
async def test_groq_timeout(groq_provider, monkeypatch):
    async def mock_post(*args, **kwargs): raise httpx.TimeoutException("Timeout")
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    res = await groq_provider.analyze_application(AnalysisInput("Sys", "User", {}))
    assert res.error_code == "PROVIDER_TIMEOUT"

@pytest.mark.asyncio
async def test_groq_empty_choices(groq_provider, monkeypatch):
    class MockResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"choices": []}
    async def mock_post(*args, **kwargs): return MockResponse()
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    res = await groq_provider.analyze_application(AnalysisInput("Sys", "User", {}))
    assert res.error_code == "INVALID_PROVIDER_RESPONSE"

@pytest.mark.asyncio
async def test_groq_empty_content(groq_provider, monkeypatch):
    class MockResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": ""}}]}
    async def mock_post(*args, **kwargs): return MockResponse()
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    res = await groq_provider.analyze_application(AnalysisInput("Sys", "User", {}))
    assert res.error_code == "INVALID_PROVIDER_RESPONSE"

@pytest.mark.asyncio
async def test_groq_refusal(groq_provider, monkeypatch):
    class MockResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"refusal": "I refuse", "content": None}}]}
    async def mock_post(*args, **kwargs): return MockResponse()
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    res = await groq_provider.analyze_application(AnalysisInput("Sys", "User", {}))
    assert res.error_code == "ANALYSIS_REFUSED"

@pytest.mark.asyncio
async def test_groq_interview_success(groq_provider, monkeypatch):
    class MockResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "questions": [{
                                    "question_text": "Q1 This is a long enough question?",
                                    "category": "database",
                                    "difficulty": "easy",
                                    "purpose": "P1 Purpose is long enough.",
                                    "expected_key_points": ["K1 This point is long enough"],
                                    "source": "cv", "source_evidence": "cv mock is long enough"
                                }, {
                                    "question_text": "Q1 This is a long enough question?",
                                    "category": "database",
                                    "difficulty": "easy",
                                    "purpose": "P1 Purpose is long enough.",
                                    "expected_key_points": ["K1 This point is long enough"],
                                    "source": "cv", "source_evidence": "cv mock is long enough"
                                }, {
                                    "question_text": "Q1 This is a long enough question?",
                                    "category": "database",
                                    "difficulty": "easy",
                                    "purpose": "P1 Purpose is long enough.",
                                    "expected_key_points": ["K1 This point is long enough"],
                                    "source": "cv", "source_evidence": "cv mock is long enough"
                                }, {
                                    "question_text": "Q1 This is a long enough question?",
                                    "category": "database",
                                    "difficulty": "easy",
                                    "purpose": "P1 Purpose is long enough.",
                                    "expected_key_points": ["K1 This point is long enough"],
                                    "source": "cv", "source_evidence": "cv mock is long enough"
                                }, {
                                    "question_text": "Q1 This is a long enough question?",
                                    "category": "database",
                                    "difficulty": "easy",
                                    "purpose": "P1 Purpose is long enough.",
                                    "expected_key_points": ["K1 This point is long enough"],
                                    "source": "cv", "source_evidence": "cv mock is long enough"
                                }, {
                                    "question_text": "Q1 This is a long enough question?",
                                    "category": "database",
                                    "difficulty": "easy",
                                    "purpose": "P1 Purpose is long enough.",
                                    "expected_key_points": ["K1 This point is long enough"],
                                    "source": "cv", "source_evidence": "cv mock is long enough"
                                }, {
                                    "question_text": "Q1 This is a long enough question?",
                                    "category": "database",
                                    "difficulty": "easy",
                                    "purpose": "P1 Purpose is long enough.",
                                    "expected_key_points": ["K1 This point is long enough"],
                                    "source": "cv", "source_evidence": "cv mock is long enough"
                                }, {
                                    "question_text": "Q1 This is a long enough question?",
                                    "category": "database",
                                    "difficulty": "easy",
                                    "purpose": "P1 Purpose is long enough.",
                                    "expected_key_points": ["K1 This point is long enough"],
                                    "source": "cv", "source_evidence": "cv mock is long enough"
                                }, {
                                    "question_text": "Q1 This is a long enough question?",
                                    "category": "database",
                                    "difficulty": "easy",
                                    "purpose": "P1 Purpose is long enough.",
                                    "expected_key_points": ["K1 This point is long enough"],
                                    "source": "cv", "source_evidence": "cv mock is long enough"
                                }, {
                                    "question_text": "Q1 This is a long enough question?",
                                    "category": "database",
                                    "difficulty": "easy",
                                    "purpose": "P1 Purpose is long enough.",
                                    "expected_key_points": ["K1 This point is long enough"],
                                    "source": "cv", "source_evidence": "cv mock is long enough"
                                }]
                        })
                    }
                }],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20}
            }
            
    async def mock_post(*args, **kwargs): return MockResponse()
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    from app.schemas.interview_questions import InterviewQuestionSet
    input_data = AnalysisInput("Sys", "User", InterviewQuestionSet.model_json_schema())
    result = await groq_provider.generate_interview_questions(input_data)
    
    assert result.error_code is None
    assert result.data is not None
    assert len(result.data.questions) == 10

@pytest.mark.asyncio
async def test_groq_interview_non_json(groq_provider, monkeypatch):
    class MockResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {
                "choices": [{
                    "message": {
                        "content": "Not a JSON"
                    }
                }]
            }
            
    async def mock_post(*args, **kwargs): return MockResponse()
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    res = await groq_provider.generate_interview_questions(AnalysisInput("Sys", "User", {}))
    assert res.error_code == "INVALID_PROVIDER_RESPONSE"

@pytest.mark.asyncio
async def test_groq_interview_wrong_schema(groq_provider, monkeypatch):
    class MockResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {
                "choices": [{
                    "message": {
                        "content": json.dumps({"wrong": "field"})
                    }
                }]
            }
            
    async def mock_post(*args, **kwargs): return MockResponse()
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    res = await groq_provider.generate_interview_questions(AnalysisInput("Sys", "User", {}))
    assert res.error_code == "INVALID_PROVIDER_RESPONSE"

@pytest.mark.asyncio
async def test_groq_interview_network_error(groq_provider, monkeypatch):
    async def mock_post(*args, **kwargs):
        raise httpx.RequestError("Network dropped")
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    res = await groq_provider.generate_interview_questions(AnalysisInput("Sys", "User", {}))
    assert res.error_code == "NETWORK_ERROR"
    assert "test_key" not in (res.error_message or "")
