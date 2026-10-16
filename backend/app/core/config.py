import os
from typing import List, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

class Settings(BaseSettings):
    APP_ENV: str = "development"
    DEBUG: bool = False

    PROJECT_NAME: str = "Backend Intern Interview Platform"
    API_V1_STR: str = "/api/v1"
    
    FRONTEND_ORIGINS: Union[List[str], str] = ["http://localhost:3000"]
    CORS_ORIGINS: Union[List[str], str, None] = None

    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "interview_db"
    
    DATABASE_URL: str | None = None
    
    STORAGE_ROOT: str = "data/uploads/cv"
    MAX_UPLOAD_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB
    
    # AI Provider config
    AI_PROVIDER: str = "groq"
    GROQ_API_KEY: str | None = None
    AI_MODEL: str = "qwen/qwen3.8-27b"
    GROQ_MODEL: str | None = None
    AI_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_BASE_URL: str | None = None
    # Gemini uses its native Generative Language API rather than the
    # OpenAI-compatible Groq endpoint. Keep its model and URL separate so a
    # provider switch cannot accidentally send a Gemini key to Groq (or vice
    # versa).
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-flash-lite-latest"
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"
    AI_REQUEST_TIMEOUT_SECONDS: int = 30
    AI_MAX_COMPLETION_TOKENS: int = 8192
    
    # AI Token & Char limits
    AI_MAX_CV_CHARS: int = 8000
    AI_MAX_JD_CHARS: int = 4000
    AI_MAX_TOTAL_CHARS: int = 12000
    AI_MAX_INTERVIEW_INPUT_CHARS: int = 20000
    AI_MAX_EVALUATION_QUESTIONS_CHARS: int = 5000
    AI_MAX_EVALUATION_ANSWERS_CHARS: int = 20000
    AI_MAX_EVALUATION_KEY_POINTS_CHARS: int = 6000
    AI_MAX_EVALUATION_TOTAL_PROMPT_CHARS: int = 35000

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    @model_validator(mode="after")
    def validate_and_sync(self):
        # 1. Normalize FRONTEND_ORIGINS
        if isinstance(self.FRONTEND_ORIGINS, str):
            val = self.FRONTEND_ORIGINS.strip()
            if val.startswith("[") and val.endswith("]"):
                import json
                try:
                    parsed = json.loads(val)
                    self.FRONTEND_ORIGINS = [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    self.FRONTEND_ORIGINS = [item.strip() for item in val[1:-1].split(",") if item.strip()]
            else:
                self.FRONTEND_ORIGINS = [item.strip() for item in val.split(",") if item.strip()]

        # Backward compatibility for CORS_ORIGINS
        if self.CORS_ORIGINS is not None:
            if isinstance(self.CORS_ORIGINS, str):
                val = self.CORS_ORIGINS.strip()
                if val.startswith("[") and val.endswith("]"):
                    import json
                    try:
                        parsed = json.loads(val)
                        self.CORS_ORIGINS = [str(item).strip() for item in parsed if str(item).strip()]
                    except Exception:
                        self.CORS_ORIGINS = [item.strip() for item in val[1:-1].split(",") if item.strip()]
                else:
                    self.CORS_ORIGINS = [item.strip() for item in val.split(",") if item.strip()]
            if self.FRONTEND_ORIGINS == ["http://localhost:3000"] and self.CORS_ORIGINS:
                self.FRONTEND_ORIGINS = self.CORS_ORIGINS
        else:
            self.CORS_ORIGINS = list(self.FRONTEND_ORIGINS)

        # 2. Sync AI_MODEL / GROQ_MODEL
        if self.GROQ_MODEL is not None and self.AI_MODEL == "openai/gpt-oss-20b":
            self.AI_MODEL = self.GROQ_MODEL
        else:
            self.GROQ_MODEL = self.AI_MODEL

        # Sync AI_BASE_URL / GROQ_BASE_URL
        if self.GROQ_BASE_URL is not None and self.AI_BASE_URL == "https://api.groq.com/openai/v1":
            self.AI_BASE_URL = self.GROQ_BASE_URL
        else:
            self.GROQ_BASE_URL = self.AI_BASE_URL

        # 3. Production validation (Fail-fast with safe error messages)
        env = self.APP_ENV.lower()
        if env == "production":
            required_fields = {
                "FRONTEND_ORIGINS": "FRONTEND_ORIGINS",
                "POSTGRES_PASSWORD": "POSTGRES_PASSWORD",
                "AI_PROVIDER": "AI_PROVIDER",
            }
            missing_fields = [
                label for field, label in required_fields.items()
                if field not in self.model_fields_set
            ]
            if missing_fields:
                raise ValueError(
                    "Cấu hình production thiếu biến bắt buộc: "
                    + ", ".join(missing_fields)
                    + "."
                )

            if self.DEBUG:
                raise ValueError("Cấu hình không hợp lệ: DEBUG không được bật trong môi trường production.")

            if not self.FRONTEND_ORIGINS:
                raise ValueError("Cấu hình không hợp lệ: FRONTEND_ORIGINS không được để trống trong môi trường production.")

            if "*" in self.FRONTEND_ORIGINS:
                raise ValueError("Cảnh báo bảo mật: FRONTEND_ORIGINS không được dùng wildcard '*' trong môi trường production.")

            if not self.POSTGRES_PASSWORD.strip() or "change_me" in self.POSTGRES_PASSWORD.lower():
                raise ValueError("Cấu hình không hợp lệ: POSTGRES_PASSWORD production chưa được thiết lập an toàn.")

            provider = self.AI_PROVIDER.lower()
            if provider not in {"groq", "gemini"}:
                raise ValueError("Cấu hình không hợp lệ: production chỉ hỗ trợ AI_PROVIDER='groq' hoặc 'gemini'.")

            required_key = self.GROQ_API_KEY if provider == "groq" else self.GEMINI_API_KEY
            required_key_name = "GROQ_API_KEY" if provider == "groq" else "GEMINI_API_KEY"
            if (
                not required_key
                or required_key.strip() == ""
                or "your_" in required_key.lower()
                or "change_me" in required_key.lower()
            ):
                raise ValueError(
                    f"Cấu hình không hợp lệ: {required_key_name} phải được thiết lập khi AI_PROVIDER là '{provider}' trong production."
                )

            if not self.STORAGE_ROOT or self.STORAGE_ROOT.strip() == "":
                raise ValueError("Cấu hình không hợp lệ: STORAGE_ROOT không được để trống.")

        return self

    def get_active_model(self) -> str:
        """Return the model name belonging to the selected external provider."""
        return self.GEMINI_MODEL if self.AI_PROVIDER.lower() == "gemini" else self.GROQ_MODEL or self.AI_MODEL

    def get_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        from sqlalchemy.engine import URL
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB
        ).render_as_string(hide_password=False)

settings = Settings()
