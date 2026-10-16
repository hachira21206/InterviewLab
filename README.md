# Backend Intern Interview Platform

Nền tảng hỗ trợ luyện phỏng vấn kỹ thuật dành cho sinh viên và Intern ứng tuyển vị trí **Backend Developer Intern**, tích hợp AI phân tích CV, sinh bộ câu hỏi và chấm điểm chi tiết.

## Phạm vi tính năng hoàn thành (Tasks 01 - 11)
1. **Task 01 — Quản lý tải lên CV an toàn**: Upload file PDF/DOCX (tối đa 5MB), kiểm tra magic bytes, lưu trữ file cục bộ an toàn, quản lý checksum SHA-256 trong PostgreSQL.
2. **Task 02 — Trích xuất văn bản CV (Extraction)**: Trích xuất nội dung bằng `pypdf` và `python-docx` cục bộ (tối đa 50 trang, 100,000 ký tự). Từ chối file PDF scan không có text layer.
3. **Task 03 — Tạo hồ sơ ứng tuyển (Job Application)**: Liên kết CV đã trích xuất với vị trí "Backend Developer Intern", Job Description tùy chọn (50 - 20,000 ký tự), hỗ trợ cập nhật qua PATCH.
4. **Task 04 — Phân tích hồ sơ bằng AI (Candidate Analysis)**: Tích hợp Groq API structured outputs (`CandidateAnalysis`), kiểm tra consent, kiểm tra budget ký tự, ẩn thông tin liên hệ (Email, SĐT).
5. **Task 05 — Sinh 10 câu hỏi phỏng vấn Backend Intern**: Phân bố 10 câu theo 5 nhóm chủ đề (Backend fundamentals, CV-based, Database, API/web/security, Scenarios/troubleshooting).
6. **Task 06 — Thực hiện phỏng vấn tuần tự**: Trả lời từng câu bằng văn bản tiếng Việt (10 - 2,000 ký tự) hoặc bỏ qua (`is_skipped`), xử lý xung đột kết thúc câu thứ 10, bảo mật resume pointer qua `sessionStorage`.
7. **Task 07 — Đánh giá câu trả lời và tạo báo cáo phỏng vấn**:
   - Rubric 5 tiêu chí: Technical accuracy (0–4), Completeness (0–2), Reasoning clarity (0–2), Relevance (0–1), Practical example (0–1) tổng 10 điểm/câu.
   - Câu bỏ qua nhận 0.0 điểm xác định (deterministic) không tốn token AI.
   - Báo cáo tổng thể: Tổng điểm (/100), Điểm trung bình (/10), Xếp loại sẵn sàng, phân tích điểm mạnh, lỗ hổng và kế hoạch học tập.
   - Trạng thái Zero-orphan tuyệt đối trên toàn bộ 8 bảng cơ sở dữ liệu.
8. **Task 08 — Lịch sử phỏng vấn và luyện lại nhiều lần**:
   - Mở rộng quan hệ `JobApplication` (1) -> `InterviewSession` (N).
   - Mỗi lần luyện là một attempt độc lập (attempt_number 1, 2, 3...) với 10 câu hỏi, câu trả lời và đánh giá riêng biệt.
   - Partial unique index đảm bảo tại mỗi thời điểm chỉ có tối đa 1 phiên đang hoạt động (`generating`, `generation_failed`, `ready`, `in_progress`).
   - Khóa bi quan ngắn hạn (row-level lock) chống race condition tạo concurrent attempt.
9. **Task 09 — Dashboard tiến bộ và so sánh các lần phỏng vấn**:
   - Endpoint `GET /api/v1/job-applications/{application_id}/interview-progress`: Tổng hợp các attempt đã đánh giá của hồ sơ ứng tuyển.
   - Hoàn toàn xác định (deterministic), không gọi AI, không lưu thêm bảng cơ sở dữ liệu mới.
   - Hợp đồng làm tròn điểm số `ROUND_HALF_UP` và Decimal aggregation (Task 09C, 09D) loại bỏ hoàn toàn sai số tích lũy nhị phân floating-point.
10. **Task 11 — Đóng gói, cấu hình và chuẩn bị triển khai ứng dụng web**:
    - Phân tách cấu hình chuẩn Development và Production với fail-fast an toàn.
    - Dockerfile đa tầng tối ưu cho Frontend (Node.js 20 Alpine, standalone mode, non-root user).
    - Dockerfile cho Backend (Python 3.11-slim, non-root user, layer caching, entrypoint fail-fast migration).
    - `docker-compose.prod.yml` chạy production-like stack (PostgreSQL, Backend, Frontend) hoàn toàn độc lập với dev stack.
    - Logging có cấu trúc, tự động che giấu (redact) các dữ liệu nhạy cảm (API keys, passwords, bearer tokens).
    - Healthchecks tự động cho toàn bộ service, đảm bảo thứ tự khởi động an toàn và graceful shutdown.

---

## Cấu trúc thư mục
- `frontend/`: Ứng dụng Next.js (App Router, TypeScript, TailwindCSS, Dockerfile multi-stage)
- `backend/`: API FastAPI (Python 3.11+, SQLAlchemy asyncpg, Alembic migrations, Dockerfile)
- `docs/`: Tài liệu kiến trúc (`architecture.md`) và môi trường/dọn dẹp (`environment-and-cleanup.md`)
- `data/`: Nơi lưu trữ file CV tải lên (`data/uploads/cv`)
- `.scratch/`: Môi trường giả lập cho Playwright E2E tests và test persistence
- `docker-compose.yml`: Compose cho môi trường Development (PostgreSQL)
- `docker-compose.prod.yml`: Compose cho môi trường Production-like (PostgreSQL, Backend, Frontend)

---

## Yêu cầu môi trường
- Python 3.11+
- Node.js 20.9.0+ (npm)
- Docker & Docker Compose v2+

---

## Hướng dẫn Khởi chạy Môi trường Development

### 1. Tạo tệp môi trường
```powershell
Copy-Item .env.example .env
```
Chỉnh sửa `.env`: để chạy offline, giữ `AI_PROVIDER=fake`. Để gọi AI thật, chọn
một provider: `AI_PROVIDER=groq` kèm `GROQ_API_KEY`, hoặc `AI_PROVIDER=gemini`
kèm `GEMINI_API_KEY`. Gemini Free tier vẫn có quota/rate limit; không commit API key.

### 2. Khởi động PostgreSQL Dev
```powershell
docker compose up -d postgres
```

### 3. Cài đặt và chạy Backend
```powershell
# Chạy migration
.\backend\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head

# Khởi động backend uvicorn
$env:PYTHONPATH="$PWD\backend"; .\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Cài đặt và chạy Frontend
```powershell
cd frontend
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm ci
npm run dev
```
Truy cập `http://localhost:3000` trên trình duyệt.

---

## Hướng dẫn Khởi chạy Môi trường Production-like (Docker Compose)

### 1. Chuẩn bị tệp cấu hình Production
```powershell
Copy-Item .env.production.example .env
```
Cấu hình các tham số môi trường production:
- `APP_ENV=production`
- `DEBUG=false`
- `FRONTEND_ORIGINS=http://localhost:3000` (Không dùng wildcard `*`)
- `POSTGRES_PASSWORD=MatKhauBaoMat123!`
- `AI_PROVIDER=gemini` hoặc `AI_PROVIDER=groq` (production không chấp nhận `fake`)
- Khi dùng Gemini: `GEMINI_API_KEY=<khóa Gemini thật>` và tùy chọn `GEMINI_MODEL=gemini-flash-lite-latest`
- Khi dùng Groq: `GROQ_API_KEY=<khóa Groq thật>`
- `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000`

Các biến trên là bắt buộc. Compose sẽ dừng ngay nếu thiếu; các giá trị mẫu
`CHANGE_ME`, `gsk_your_...`, `AIza_your_...` cũng bị backend từ chối. Mật khẩu PostgreSQL được
truyền theo từng thành phần và được SQLAlchemy mã hóa URL an toàn, kể cả khi có
`@`, `/`, `%` hoặc `:`.

### 2. Build Docker Images sạch
```powershell
docker compose -f docker-compose.prod.yml build
```

### 3. Khởi động Stack Production
```powershell
docker compose -f docker-compose.prod.yml up -d
```
Docker Compose sẽ khởi động theo đúng thứ tự:
1. `postgres`: Khởi tạo và kiểm tra sức khỏe `pg_isready`.
2. `backend`: Đợi `postgres` healthy, tự động chạy `alembic upgrade head`, sau đó khởi động Uvicorn.
3. `frontend`: Đợi `backend` healthy, khởi động Next.js standalone server.

### 4. Xem trạng thái và logs
```powershell
# Xem trạng thái sức khỏe các service
docker compose -f docker-compose.prod.yml ps

# Xem log thời gian thực của backend
docker compose -f docker-compose.prod.yml logs -f backend

# Xem log frontend
docker compose -f docker-compose.prod.yml logs -f frontend
```

### 5. Kiểm tra Health Check trực tiếp
- API Health: `curl http://localhost:8000/api/v1/health`
- Database Connectivity Health: `curl http://localhost:8000/api/v1/health/db`
- Frontend HTTP: `curl -I http://localhost:3000/`

### 6. Dừng hoặc khởi động lại Services
```powershell
# Tạm dừng stack nhưng giữ nguyên containers và dữ liệu
docker compose -f docker-compose.prod.yml stop

# Khởi động lại một service cụ thể
docker compose -f docker-compose.prod.yml restart backend
```

---

## Quản lý Cơ sở dữ liệu & Sao lưu (Backup & Restore)

### 1. Sao lưu (Backup) PostgreSQL
```powershell
docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U postgres -d interview_db > backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql
```

### 2. Phục hồi (Restore) PostgreSQL
```powershell
cat backup_file.sql | docker compose -f docker-compose.prod.yml exec -T postgres psql -U postgres -d interview_db
```

### 3. Kiểm tra Alembic Migration Revision
```powershell
docker compose -f docker-compose.prod.yml exec backend alembic current
# Kết quả kỳ vọng: feae8be1dc16 (head)
```

---

## Dọn dẹp & Quản lý Dữ liệu (Cleanup Guidelines)

### 1. Dọn dẹp an toàn (Giữ nguyên Volume dữ liệu)
```powershell
docker compose -f docker-compose.prod.yml down
```
Lệnh này dừng và gỡ bỏ containers, networks nhưng **bảo toàn 100% volume dữ liệu** (`interview_prod_postgres_data` và `interview_prod_cv_uploads`).

### 2. CẢNH BÁO NGUY HIỂM: Dọn dẹp toàn bộ bao gồm Volume (Destructive)
> [!CAUTION]
> Lệnh dưới đây sẽ XÓA VĨNH VIỄN toàn bộ cơ sở dữ liệu và file CV tải lên. Chỉ thực hiện khi muốn reset hoàn toàn môi trường và đã sao lưu dữ liệu!
```powershell
docker compose -f docker-compose.prod.yml down -v
```

---

## Chạy Kiểm thử Toàn diện

**1. Toàn bộ Backend Pytest (278 tests bao gồm Task 11):**
```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -v
cd ..
```

**2. Frontend Lint, Type-Check, Build:**
```powershell
cd frontend
npm run type-check
npm run lint
npm run build
cd ..
```

**3. Playwright E2E UI Suite (19 Sections):**
```powershell
.\.scratch\.venv\Scripts\python.exe .scratch\test_upload_ui.py
```

**4. Persistence & Restart Integration Test:**
```powershell
.\backend\.venv\Scripts\python.exe .scratch\test_task11_persistence.py
```
