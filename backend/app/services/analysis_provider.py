from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple
import httpx
import json
from app.core.config import settings
from app.schemas.application_analysis import CandidateAnalysis
from app.schemas.interview_questions import InterviewQuestionSet
from app.schemas.interview_evaluation import InterviewEvaluationAISet
from pydantic import ValidationError
from app.core.exceptions import ProviderConfigurationError
import logging

logger = logging.getLogger(__name__)

class AnalysisInput:
    def __init__(self, system_prompt: str, user_prompt: str, schema: dict):
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.schema = schema

class AnalysisResult:
    def __init__(self, data: Optional[CandidateAnalysis], error_code: Optional[str], error_message: Optional[str], input_tokens: Optional[int] = None, output_tokens: Optional[int] = None):
        self.data = data
        self.error_code = error_code
        self.error_message = error_message
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

class InterviewQuestionsResult:
    def __init__(self, data: Optional[InterviewQuestionSet], error_code: Optional[str], error_message: Optional[str], input_tokens: Optional[int] = None, output_tokens: Optional[int] = None):
        self.data = data
        self.error_code = error_code
        self.error_message = error_message
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

class InterviewEvaluationResult:
    def __init__(self, data: Optional[InterviewEvaluationAISet], error_code: Optional[str], error_message: Optional[str], input_tokens: Optional[int] = None, output_tokens: Optional[int] = None):
        self.data = data
        self.error_code = error_code
        self.error_message = error_message
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

class AIAnalysisProvider(ABC):
    @abstractmethod
    async def analyze_application(self, input_data: AnalysisInput) -> AnalysisResult:
        pass
        
    @abstractmethod
    async def generate_interview_questions(self, input_data: AnalysisInput) -> InterviewQuestionsResult:
        pass

    @abstractmethod
    async def evaluate_interview(self, input_data: AnalysisInput) -> InterviewEvaluationResult:
        pass

import copy

def prepare_strict_json_schema(schema: dict) -> dict:
    s = copy.deepcopy(schema)
    def _fix_node(node):
        if not isinstance(node, dict):
            return
        if "properties" in node and isinstance(node["properties"], dict):
            node["required"] = list(node["properties"].keys())
            node["additionalProperties"] = False
            for child in node["properties"].values():
                _fix_node(child)
        if "$defs" in node and isinstance(node["$defs"], dict):
            for child in node["$defs"].values():
                _fix_node(child)
        if "definitions" in node and isinstance(node["definitions"], dict):
            for child in node["definitions"].values():
                _fix_node(child)
        if "items" in node:
            if isinstance(node["items"], dict):
                _fix_node(node["items"])
            elif isinstance(node["items"], list):
                for item in node["items"]:
                    _fix_node(item)
    _fix_node(s)
    return s

class GroqAnalysisProvider(AIAnalysisProvider):
    async def _call_api(self, input_data: AnalysisInput) -> Tuple[Optional[dict], Optional[str], Optional[str], Optional[int], Optional[int]]:
        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.GROQ_MODEL,
            "messages": [
                {"role": "system", "content": input_data.system_prompt},
                {"role": "user", "content": input_data.user_prompt}
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "schema": prepare_strict_json_schema(input_data.schema),
                    "strict": True
                }
            },
            "temperature": 0.1,
            "max_completion_tokens": getattr(settings, "AI_MAX_COMPLETION_TOKENS", 8192)
        }
        
        base_url = getattr(settings, 'GROQ_BASE_URL', 'https://api.groq.com/openai/v1')
        timeout = getattr(settings, 'AI_REQUEST_TIMEOUT_SECONDS', 60.0)
        
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=timeout)
                
                if res.status_code in (401, 403):
                    return None, "CONFIGURATION_ERROR", "Lỗi cấu hình xác thực AI.", None, None
                elif res.status_code == 429:
                    return None, "RATE_LIMITED", "Vượt quá giới hạn request.", None, None
                elif res.status_code == 400:
                    logger.warning("Groq API 400 Bad Request: %s", res.text)
                    return None, "INVALID_PROVIDER_RESPONSE", "Lỗi định dạng yêu cầu hoặc vượt quá giới hạn token từ AI.", None, None
                elif res.status_code >= 500:
                    return None, "PROVIDER_UNAVAILABLE", "AI Provider hiện không khả dụng.", None, None
                    
                res.raise_for_status()
                data = res.json()
                
                if not data or "choices" not in data or len(data["choices"]) == 0:
                    return None, "INVALID_PROVIDER_RESPONSE", "Phản hồi không chứa kết quả.", None, None
                    
                choice = data["choices"][0]
                message = choice.get("message", {})
                
                # Check refusal (Groq/OpenAI JSON format refusal)
                if message.get("refusal") or choice.get("finish_reason") == "stop" and not message.get("content"):
                    if message.get("refusal"):
                        return None, "ANALYSIS_REFUSED", "AI từ chối phân tích nội dung.", None, None
                
                content = message.get("content")
                if not content:
                    return None, "INVALID_PROVIDER_RESPONSE", "Nội dung phản hồi rỗng.", None, None
                    
                usage = data.get("usage", {})
                
                try:
                    parsed_json = json.loads(content)
                    return parsed_json, None, None, usage.get("prompt_tokens"), usage.get("completion_tokens")
                except json.JSONDecodeError:
                    return None, "INVALID_PROVIDER_RESPONSE", "Phản hồi không phải JSON hợp lệ.", None, None
                    
        except httpx.TimeoutException:
            return None, "PROVIDER_TIMEOUT", "Hết thời gian chờ phản hồi từ AI.", None, None
        except httpx.RequestError:
            return None, "NETWORK_ERROR", "Lỗi kết nối mạng đến AI Provider.", None, None
        except Exception:
            return None, "INTERNAL_ANALYSIS_ERROR", "Lỗi không xác định khi gọi AI.", None, None

    async def analyze_application(self, input_data: AnalysisInput) -> AnalysisResult:
        parsed_json, err_code, err_msg, in_tok, out_tok = await self._call_api(input_data)
        if err_code:
            return AnalysisResult(None, err_code, err_msg, in_tok, out_tok)
        try:
            validated_data = CandidateAnalysis(**parsed_json)
            return AnalysisResult(validated_data, None, None, in_tok, out_tok)
        except ValidationError:
            return AnalysisResult(None, "INVALID_PROVIDER_RESPONSE", "Kết quả JSON sai Schema.", in_tok, out_tok)

    async def generate_interview_questions(self, input_data: AnalysisInput) -> InterviewQuestionsResult:
        parsed_json, err_code, err_msg, in_tok, out_tok = await self._call_api(input_data)
        if err_code:
            return InterviewQuestionsResult(None, err_code, err_msg, in_tok, out_tok)
        try:
            validated_data = InterviewQuestionSet(**parsed_json)
            return InterviewQuestionsResult(validated_data, None, None, in_tok, out_tok)
        except ValidationError:
            return InterviewQuestionsResult(None, "INVALID_PROVIDER_RESPONSE", "Kết quả JSON sai Schema.", in_tok, out_tok)

    async def evaluate_interview(self, input_data: AnalysisInput) -> InterviewEvaluationResult:
        parsed_json, err_code, err_msg, in_tok, out_tok = await self._call_api(input_data)
        if err_code:
            return InterviewEvaluationResult(None, err_code, err_msg, in_tok, out_tok)
        try:
            validated_data = InterviewEvaluationAISet(**parsed_json)
            return InterviewEvaluationResult(validated_data, None, None, in_tok, out_tok)
        except ValidationError:
            return InterviewEvaluationResult(None, "INVALID_PROVIDER_RESPONSE", "Kết quả JSON sai Schema.", in_tok, out_tok)


class GeminiAnalysisProvider(AIAnalysisProvider):
    """Google Gemini native REST provider.

    Gemini's JSON-schema API differs from Groq's OpenAI-compatible endpoint,
    hence this is deliberately a separate adapter. It never puts the API key
    in the URL, which also keeps it out of proxy/access logs.
    """

    async def _call_api(self, input_data: AnalysisInput) -> Tuple[Optional[dict], Optional[str], Optional[str], Optional[int], Optional[int]]:
        payload = {
            "systemInstruction": {"parts": [{"text": input_data.system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": input_data.user_prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": getattr(settings, "AI_MAX_COMPLETION_TOKENS", 8192),
                "responseMimeType": "application/json",
                "responseJsonSchema": prepare_strict_json_schema(input_data.schema),
            },
        }
        base_url = settings.GEMINI_BASE_URL.rstrip("/")
        model = settings.GEMINI_MODEL.strip()
        timeout = getattr(settings, "AI_REQUEST_TIMEOUT_SECONDS", 60.0)
        headers = {"x-goog-api-key": settings.GEMINI_API_KEY or "", "Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    f"{base_url}/models/{model}:generateContent",
                    headers=headers,
                    json=payload,
                    timeout=timeout,
                )
                if res.status_code in (401, 403):
                    return None, "CONFIGURATION_ERROR", "Lỗi cấu hình xác thực AI.", None, None
                if res.status_code == 429:
                    return None, "RATE_LIMITED", "Vượt quá giới hạn request.", None, None
                if res.status_code == 400:
                    logger.warning("Gemini API rejected the request with HTTP 400.")
                    return None, "INVALID_PROVIDER_RESPONSE", "Lỗi định dạng yêu cầu hoặc vượt quá giới hạn token từ AI.", None, None
                if res.status_code >= 500:
                    return None, "PROVIDER_UNAVAILABLE", "AI Provider hiện không khả dụng.", None, None
                res.raise_for_status()
                data = res.json()

            usage = data.get("usageMetadata", {}) if isinstance(data, dict) else {}
            candidates = data.get("candidates", []) if isinstance(data, dict) else []
            if not candidates:
                return None, "ANALYSIS_REFUSED", "AI từ chối phân tích nội dung.", None, None
            parts = candidates[0].get("content", {}).get("parts", [])
            content = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
            if not content:
                return None, "INVALID_PROVIDER_RESPONSE", "Nội dung phản hồi rỗng.", None, None
            try:
                return (
                    json.loads(content),
                    None,
                    None,
                    usage.get("promptTokenCount"),
                    usage.get("candidatesTokenCount"),
                )
            except json.JSONDecodeError:
                return None, "INVALID_PROVIDER_RESPONSE", "Phản hồi không phải JSON hợp lệ.", None, None
        except httpx.TimeoutException:
            return None, "PROVIDER_TIMEOUT", "Hết thời gian chờ phản hồi từ AI.", None, None
        except httpx.RequestError:
            return None, "NETWORK_ERROR", "Lỗi kết nối mạng đến AI Provider.", None, None
        except Exception:
            logger.exception("Gemini provider returned an unexpected response.")
            return None, "INTERNAL_ANALYSIS_ERROR", "Lỗi không xác định khi gọi AI.", None, None

    async def analyze_application(self, input_data: AnalysisInput) -> AnalysisResult:
        data, code, message, input_tokens, output_tokens = await self._call_api(input_data)
        if code:
            return AnalysisResult(None, code, message, input_tokens, output_tokens)
        try:
            return AnalysisResult(CandidateAnalysis(**data), None, None, input_tokens, output_tokens)
        except ValidationError:
            return AnalysisResult(None, "INVALID_PROVIDER_RESPONSE", "Kết quả JSON sai Schema.", input_tokens, output_tokens)

    async def generate_interview_questions(self, input_data: AnalysisInput) -> InterviewQuestionsResult:
        data, code, message, input_tokens, output_tokens = await self._call_api(input_data)
        if code:
            return InterviewQuestionsResult(None, code, message, input_tokens, output_tokens)
        try:
            return InterviewQuestionsResult(InterviewQuestionSet(**data), None, None, input_tokens, output_tokens)
        except ValidationError:
            return InterviewQuestionsResult(None, "INVALID_PROVIDER_RESPONSE", "Kết quả JSON sai Schema.", input_tokens, output_tokens)

    async def evaluate_interview(self, input_data: AnalysisInput) -> InterviewEvaluationResult:
        data, code, message, input_tokens, output_tokens = await self._call_api(input_data)
        if code:
            return InterviewEvaluationResult(None, code, message, input_tokens, output_tokens)
        try:
            return InterviewEvaluationResult(InterviewEvaluationAISet(**data), None, None, input_tokens, output_tokens)
        except ValidationError:
            return InterviewEvaluationResult(None, "INVALID_PROVIDER_RESPONSE", "Kết quả JSON sai Schema.", input_tokens, output_tokens)

class FakeAnalysisProvider(AIAnalysisProvider):
    def __init__(self):
        self.call_count = 0
        self.mock_result: Optional[AnalysisResult] = None
        self.mock_questions_result: Optional[InterviewQuestionsResult] = None
        self.mock_evaluation_result: Optional[InterviewEvaluationResult] = None
        
    async def analyze_application(self, input_data: AnalysisInput) -> AnalysisResult:
        self.call_count += 1
        if self.mock_result:
            return self.mock_result
            
        mock_data = CandidateAnalysis(
            summary_vi="Mock summary",
            candidate_level="junior_ready",
            technical_skills=[],
            projects=[],
            education=[],
            strengths=[],
            gaps=[],
            matched_requirements=[],
            missing_requirements=[],
            recommended_interview_topics=[],
            language_detected="vi",
            warnings=[]
        )
        return AnalysisResult(data=mock_data, error_code=None, error_message=None, input_tokens=100, output_tokens=50)

    async def generate_interview_questions(self, input_data: AnalysisInput) -> InterviewQuestionsResult:
        self.call_count += 1
        if self.mock_questions_result:
            return self.mock_questions_result
            
        from app.models.interview_question import QuestionCategory, QuestionDifficulty, QuestionSource
        from app.schemas.interview_questions import InterviewQuestionGenerated
        
        questions = []
        cats = [
            "backend_fundamentals", "backend_fundamentals",
            "cv_project_experience", "cv_project_experience",
            "database", "database",
            "api_web_design", "api_web_design",
            "debugging_problem_solving", "behavioral_teamwork"
        ]
        diffs = ["easy"] * 4 + ["medium"] * 4 + ["hard"] * 2
        for i in range(10):
            q = InterviewQuestionGenerated(
                question_text=f"Valid question text {i}",
                category=QuestionCategory(cats[i]),
                difficulty=QuestionDifficulty(diffs[i]),
                purpose="Valid purpose text for this question",
                expected_key_points=["Key point 1"],
                source=QuestionSource.general_backend,
                source_evidence="evidence" if cats[i] == "cv_project_experience" else None
            )
            questions.append(q)
            
        mock_data = InterviewQuestionSet(questions=questions)
        return InterviewQuestionsResult(data=mock_data, error_code=None, error_message=None, input_tokens=100, output_tokens=50)

    async def evaluate_interview(self, input_data: AnalysisInput) -> InterviewEvaluationResult:
        self.call_count += 1
        if self.mock_evaluation_result:
            return self.mock_evaluation_result
            
        from app.models.interview_evaluation import EvaluationConfidence
        from app.schemas.interview_evaluation import QuestionEvaluationAI, InterviewEvaluationAISet
        
        evals = []
        for i in range(1, 11):
            q_eval = QuestionEvaluationAI(
                question_order=i,
                technical_accuracy=3.5,
                completeness=1.5,
                reasoning_clarity=1.5,
                relevance=1.0,
                practical_example=0.5,
                total_score=8.0,
                feedback=f"Câu trả lời số {i} thể hiện hiểu biết tốt về khái niệm backend.",
                strengths=["Hiểu rõ khái niệm", "Lập luận logic"],
                missing_points=["Cần làm rõ thêm về hiệu năng"],
                suggested_answer=f"Câu trả lời gợi ý chi tiết cho câu {i}.",
                study_topics=["Backend Architecture", "Concurrency"],
                confidence=EvaluationConfidence.high
            )
            evals.append(q_eval)
            
        mock_data = InterviewEvaluationAISet(
            evaluations=evals,
            overall_summary="Ứng viên có kiến thức nền tảng tốt, tư duy giải quyết vấn đề mạch lạc.",
            key_strengths=["Nắm vững nguyên lý cơ bản", "Kỹ năng lập trình tốt"],
            knowledge_gaps=["Kinh nghiệm tối ưu hóa cơ sở dữ liệu"],
            priority_improvements=["Thực hành thiết kế API chuẩn REST"],
            recommended_study_topics=["Database Indexing", "Caching with Redis"],
            short_term_study_plan=["Tuần 1: Ôn tập DB indexing", "Tuần 2: Viết test case"],
            next_interview_advice="Tự tin hơn khi giải thích các lựa chọn thiết kế."
        )
        return InterviewEvaluationResult(data=mock_data, error_code=None, error_message=None, input_tokens=100, output_tokens=50)

def get_analysis_provider() -> AIAnalysisProvider:
    provider = settings.AI_PROVIDER.lower()
    if provider == "groq":
        if not settings.GROQ_API_KEY:
            raise ProviderConfigurationError("Chưa cấu hình GROQ_API_KEY.")
        return GroqAnalysisProvider()
    if provider == "gemini":
        if not settings.GEMINI_API_KEY:
            raise ProviderConfigurationError("Chưa cấu hình GEMINI_API_KEY.")
        return GeminiAnalysisProvider()
    raise ProviderConfigurationError(f"Provider không hỗ trợ: {settings.AI_PROVIDER}")
