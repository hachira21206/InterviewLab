# Kiến trúc hệ thống

## Tổng quan thành phần
1. **Frontend (Next.js App Router)**: UI hiển thị phía client, giao tiếp với backend thông qua REST API.
2. **Backend (FastAPI)**: API Server xử lý logic, quản lý kết nối database bằng Async SQLAlchemy (asyncpg).
3. **Database (PostgreSQL)**: Cơ sở dữ liệu quan hệ, được chạy bằng Docker Compose cho môi trường dev.

## Luồng frontend gọi backend
- Frontend gọi API backend thông qua Fetch API. URL của backend được thiết lập bằng biến môi trường `NEXT_PUBLIC_BACKEND_URL`.
- Xử lý lỗi nghiêm ngặt: Kiểm tra `content-type`, kiểm tra HTTP status, áp dụng type guards đầy đủ trước khi đưa dữ liệu vào React state.
- Hỗ trợ hủy request qua `AbortController` khi component unmount.

## Chiến lược nhất quán File & Database (Task 01)
Khi người dùng tải CV lên hệ thống, luồng dữ liệu tuân thủ quy tắc sau để tránh dữ liệu mồ côi (orphan data):
1. Nhận file stream, ghi tạm vào `data/uploads/cv/tmp_<uuid>` đồng thời tính toán SHA-256. Nếu dung lượng > 5MB, xóa file tạm và từ chối.
2. Kiểm tra file content (Magic bytes với PDF, cấu trúc ZIP an toàn với DOCX). Nếu lỗi, xóa file tạm.
3. Đổi tên file tạm thành `<uuid>.ext` (rename atomic).
4. Khởi tạo transaction database tạo record `cv_documents`.
5. Nếu commit database thất bại, xóa file đã đổi tên (rollback storage).
6. File trên file system luôn được tạo trước và xóa nếu metadata không lưu được, không bao giờ có trường hợp Database có nhưng File không có.

## Task 02 - Extraction
- Extractor Service xử lý PDF/DOCX bằng thư viện cục bộ (pypdf, python-docx) không dùng AI bên ngoài.
- `CVTextExtractor` điều phối parser đồng bộ qua `asyncio.to_thread` để tránh block event loop.
- Trạng thái `uploaded`, `extracting`, `extracted`, `extraction_failed` được kiểm soát chặt chẽ.
- Áp dụng Pydantic V2 schemas và type guards.

## Task 03 - Job Application
- Quan hệ `cv_documents` 1 -> N `job_applications` qua Foreign Key `cv_document_id` (`ON DELETE CASCADE`).
- `target_role` cố định: "Backend Developer Intern".
- `job_description` không bắt buộc (nullable trong DB).
- `interview_language` mặc định là `vi`.
- Yêu cầu CV phải ở trạng thái `extracted` trước khi tạo Job Application.

## Task 04 - AI Analysis Architecture
- **Provider Interface**: Dùng `AIAnalysisProvider` trừu tượng (`GroqAnalysisProvider`, `GeminiAnalysisProvider`, `FakeAnalysisProvider`).
- **API Integration**: Dùng `httpx` trực tiếp, không cài thêm AI SDK. Groq dùng endpoint OpenAI-compatible; Gemini dùng native Generative Language API với `x-goog-api-key` header.
- **Structured Output**: JSON Schema từ Pydantic được truyền qua `response_format` của Groq hoặc `responseJsonSchema` của Gemini; kết quả luôn được Pydantic validate lại ở backend.
- **State Machine**: Trạng thái analysis (`pending`, `analyzing`, `completed`, `failed`) quản lý qua bảng `application_analyses`. Claim nguyên tử chống concurrent requests.
- **Data Privacy**: CV text được gỡ bỏ Email và SĐT thông qua regex trước khi chèn vào Prompt. Không gửi CV gốc thô.

## Task 05 - Interview Question Generation
- **Target Role**: Backend Developer Intern.
- **Sinh chính xác 10 câu hỏi**:
  - 2 câu backend fundamentals.
  - 2 câu trực tiếp từ CV (kỹ năng, dự án).
  - 2 câu database.
  - 2 câu API/web/bảo mật backend cơ bản.
  - 2 câu tình huống/tư duy xử lý sự cố.
- **Input Budget**: Kiểm tra giới hạn ký tự CV, JD và prompt trước khi claim session để tránh lỗi token hoặc timeout.
- **Transaction Isolation**: Kiểm tra cấu hình và claim session nguyên tử trước khi gọi Groq; giải phóng DB transaction trong khi gọi AI bên ngoài.
- **Schema & Migration**: Lưu phiên phỏng vấn trong `interview_sessions` và từng câu hỏi trong `interview_questions`.

## Task 06 - Interview Execution & Text Responses
- **Tiến trình tuần tự**: Thực hiện 10 câu hỏi theo thứ tự `order_index` từ 1 đến 10. Không cho phép trả lời câu N+1 khi câu N chưa xong.
- **Quyền lựa chọn**: Mỗi câu có thể trả lời bằng văn bản tiếng Việt (10 - 2,000 ký tự) hoặc bỏ qua (`is_skipped=True`).
- **Chống race condition câu 10**: Nhánh xử lý xung đột commit kiểm tra session status; rollback và kiểm tra lại trạng thái trước khi cho phép cập nhật, đảm bảo request về sau không ghi đè lên session đã hoàn thành.
- **Bảo mật phục hồi trạng thái (Resume Pointer)**:
  - Chỉ lưu Resume Pointer phiên bản 1 tối thiểu gồm `cv_document_id` và `job_application_id` trong `sessionStorage`.
  - Tuyệt đối không lưu CV text, JD, câu hỏi, câu trả lời, hay báo cáo AI vào browser storage.
  - Phục hồi an toàn qua backend validation và atomic UI state update.

## Task 07 - AI Evaluation & Interview Report
- **Đối tượng**: Đánh giá toàn bộ 10 câu trả lời của các session có trạng thái `completed`.
- **Khung chấm điểm (Rubric) cố định theo thang điểm 10**:
  - `technical_accuracy`: 0 - 4.0 điểm.
  - `completeness`: 0 - 2.0 điểm.
  - `reasoning_clarity`: 0 - 2.0 điểm.
  - `relevance`: 0 - 1.0 điểm.
  - `practical_example`: 0 - 1.0 điểm.
  - `total_score`: Tổng chính xác của 5 tiêu chí trên (0 - 10.0 điểm).
- **Xử lý câu bỏ qua (Deterministic)**: Tất cả câu có `is_skipped=True` nhận 0.0 điểm cho mọi tiêu chí mà không cần gửi đến AI, giảm tiêu tốn token và tăng tính dự đoán.
- **Báo cáo tổng hợp**:
  - `total_score`: Tổng điểm toàn buổi (thang 100).
  - `average_score`: Điểm trung bình (thang 10).
  - `readiness_level`: Xếp loại theo ngưỡng điểm: `intern_ready` (>= 7.0), `needs_improvement` (5.0 - 6.9), `not_ready` (< 5.0).
  - Điểm trung bình theo từng category.
  - Điểm mạnh chính, lỗ hổng kiến thức, kế hoạch học tập ngắn hạn và lời khuyên phỏng vấn tiếp theo.
- **Bảo toàn dữ liệu & Zero-Orphan**:
  - Bảng `interview_evaluations` và `interview_response_evaluations` có Foreign Key cascade (`ON DELETE CASCADE`).
  - Toàn bộ 8 bảng trong cơ sở dữ liệu duy trì tính toàn vẹn và sạch sẽ dữ liệu.

## Task 08 - Interview History & Multiple Attempts
- **Mô hình 1-N**:
  - Chuyển đổi quan hệ giữa `JobApplication` và `InterviewSession` từ một-một thành một-nhiều.
  - Bỏ unique constraint cũ trên `job_application_id`.
  - Bổ sung `attempt_number` (integer, >= 1, not null).
  - Ràng buộc duy nhất `UNIQUE(job_application_id, attempt_number)` đảm bảo mỗi lần luyện có số thứ tự tăng dần duy nhất.
- **Ràng buộc Partial Unique Index ở mức Database**:
  - `uq_interview_sessions_active_attempt`: Partial unique index trên `(job_application_id)` với điều kiện `WHERE status IN ('generating', 'generation_failed', 'ready', 'in_progress')`.
  - Đảm bảo tại một thời điểm, một hồ sơ ứng tuyển chỉ có tối đa duy nhất một phiên chưa hoàn thành, ngăn chặn hoàn toàn việc tạo nhiều phiên dở dang hoặc spam request.
- **Nguyên tử và Chống Race Condition**:
  - Khi bắt đầu tạo attempt mới (`POST /attempts`), backend dùng câu lệnh ngắn hạn `SELECT ... FOR UPDATE` trên bảng `job_applications`.
  - Transaction ngắn: kiểm tra điều kiện không có active attempt, cấp phát `attempt_number = max_existing + 1`, commit claim session mới với trạng thái `generating`.
  - Quá trình gọi AI Provider (`GroqAnalysisProvider.generate_interview_questions`) được thực hiện ngoài transaction để không giữ DB connection.
- **Ngữ nghĩa Endpoint `/current`**:
  - Ưu tiên 1: Trả về phiên active (`generating`, `generation_failed`, `ready`, `in_progress`) nếu có.
  - Ưu tiên 2: Nếu tất cả phiên đều đã `completed`, trả về phiên `completed` mới nhất (attempt_number lớn nhất).
  - Trả về 404 nếu ứng tuyển chưa có bất kỳ phiên phỏng vấn nào.
- **Bảo mật và Type Guard**:
  - API `GET /api/v1/job-applications/{application_id}/interview-sessions` trả về lịch sử tóm tắt (không kèm `expected_key_points`, đáp án mẫu, hoặc prompt nội bộ).
  - Frontend type guards kiểm tra và từ chối nghiêm ngặt nếu API response lịch sử chứa bất kỳ trường nhạy cảm nào bị rò rỉ.
- **Migration & Downgrade Safety**:
  - Migration script `feae8be1dc16` gắn `attempt_number = 1` cho các session cũ.
  - Downgrade kiểm tra an toàn: nếu database đã phát sinh multiple attempts (> 1), lệnh downgrade sẽ từ chối thực hiện để bảo vệ dữ liệu lịch sử người dùng.

## Task 09 - Progress Dashboard & Cross-Attempt Comparison
- **Mục tiêu**:
  - Tổng hợp và so sánh kết quả các phiên luyện phỏng vấn độc lập của một `JobApplication`.
  - Phân tích xu hướng điểm số theo thời gian và đánh giá tiến độ theo từng nhóm kỹ năng (`QuestionCategory`).
- **Nguyên tắc tính toán & Deterministic Processing**:
  - Toàn bộ số liệu được tổng hợp trực tiếp từ các bảng `interview_sessions`, `interview_evaluations`, `interview_response_evaluations` có trạng thái:
    - `interview_sessions.status = 'completed'`
    - Có evaluation hợp lệ với `status = 'evaluated'`, `total_score` (0-100), `average_score` (0-10), và `readiness_level` hợp lệ.
    - `answered_count` + `skipped_count` = 10.
  - Các attempt dở dang (`generating`, `in_progress`, `generation_failed`, `pending`, `evaluation_failed`) được tự động bỏ qua khỏi thống kê so sánh mà không gây lỗi.
  - **Zero AI Calls**: Không gọi Groq API, không tiêu tốn token AI, không yêu cầu consent AI khi xem tiến độ.
  - **Zero Database Schema Change**: Không thêm bảng cơ sở dữ liệu mới; Alembic head duy trì `feae8be1dc16`.
  - **Zero N+1 Query**: Backend sử dụng đúng 2 query cố định (1 query xác minh `JobApplication`, 1 query lấy danh sách `interview_sessions` kết hợp `joinedload(InterviewSession.evaluation)` với filter và ordering chặt chẽ), đảm bảo chi phí truy vấn O(1) bất kể số lượng attempt.
- **Công thức tính toán & Làm tròn**:
  - Điểm số và delta được làm tròn 2 chữ số thập phân (`round(..., 2)`).
  - Phân loại trạng thái so sánh:
    - `no_data`: 0 attempt hợp lệ.
    - `insufficient_data`: 1 attempt hợp lệ.
    - `improved`: `latest_vs_previous.total_score_delta >= 0.01`.
    - `declined`: `latest_vs_previous.total_score_delta <= -0.01`.
    - `unchanged`: `|latest_vs_previous.total_score_delta| < 0.01`.
  - Hướng thay đổi mức độ sẵn sàng (`readiness_direction`):
    - Đánh giá theo đúng 4 bậc chuẩn của `ReadinessLevel`: `needs_foundation` (1) < `developing` (2) < `intern_ready` (3) < `strong_intern_candidate` (4).
    - So sánh bậc giữa attempt sau và attempt trước để xác định `improved`, `declined`, hoặc `unchanged`.
    - `readiness_changed` được xác định bằng phép so sánh bình đẳng (`latest.readiness_level != target.readiness_level`).
  - Tiến độ theo kỹ năng (`category_progress`):
    - Tính `first_score`, `previous_score`, `latest_score`, deltas theo từng nhóm kỹ năng.
    - Xử lý dữ liệu an toàn: nếu attempt trước hoặc đầu tiên không có câu hỏi thuộc nhóm kỹ năng đó, giá trị được trả về `None` / `null` và frontend hiển thị nhãn thân thiện `"Chưa có dữ liệu"`.
- **Frontend Dashboard & Zero Heavy Dependency**:
  - Component `InterviewProgressDashboard.tsx` tự dựng biểu đồ SVG nhẹ đáp ứng responsive, không cài thêm thư viện biểu đồ ngoài (Recharts, Chart.js, D3).
  - Trục Y cố định 0-100 với các đường lưới mốc 0, 25, 50, 75, 100 điểm, điểm số và số lần luyện hiển thị rõ ràng.
  - Thẻ tổng quan, huy hiệu delta trực quan (+/-, mũi tên ↑/↓/→), bảng tiến bộ kỹ năng.
  - Type guard `isInterviewProgressReportResponse` kiểm tra nghiêm ngặt tính hợp lệ của UUID, bounds của điểm số và counts, tính tăng dần của attempt, và đối chiếu chéo (cross-verify) tính nhất quán toán học giữa trend và delta (sai lệch < 0.01).
  - Ngăn ngừa rò rỉ dữ liệu nhạy cảm: từ chối mọi payload chứa `expected_key_points`, đáp án mẫu hoặc dữ liệu nội bộ.
  - Vòng đời an toàn: quản lý `AbortController` hủy fetch khi unmount hoặc khi bấm làm mới, ngăn ngừa rò rỉ bộ nhớ và cascading render warnings.

## Hợp đồng làm tròn điểm số (Rounding Contract - Task 09C)
- **Chuẩn làm tròn được chọn**: `ROUND_HALF_UP` (nửa cent làm tròn lên theo hướng xa số 0: $\ge 5 \to$ lên).
- **Lý do không dùng Python `round(float)`**:
  - Python built-in `round()` áp dụng cơ chế Banker's Rounding (`ROUND_HALF_EVEN`) kết hợp với biểu diễn nhị phân IEEE-754 của `float`.
  - Phép chia `26.75 / 10.0` trong Python float cho kết quả `2.6749999999999998` dẫn tới `round(..., 2) = 2.67`.
  - Tương tự, `72.25 / 10.0` dẫn tới `7.22`.
- **Lý do không dùng JavaScript `Math.round(val * 100)` đơn lẻ**:
  - Biểu diễn nhị phân IEEE-754 của JavaScript cũng gặp sai số tích lũy: ví dụ `1.005 * 100` ra `100.49999999999999`, nếu gọi `Math.round()` đơn thuần sẽ cho `100` (`1.00`) thay vì `101` (`1.01`).
  - Phép chia `0.85 / 10` trong JavaScript ra `0.08499999999999999`, dẫn tới kết quả sai lệch so với phân số thập phân chuẩn.
- **Các ca nửa cent chuẩn mực**:
  - `26.75 / 10 = 2.675` $\to$ **`2.68`** (trước đây Python float ra `2.67`).
  - `72.25 / 10 = 7.225` $\to$ **`7.23`** (trước đây Python float ra `7.22`).
  - `27.25 / 10 = 2.725` $\to$ **`2.73`**.
  - `72.75 / 10 = 7.275` $\to$ **`7.28`**.
  - `0.0` $\to$ `0.00`, `100.0` $\to$ `10.00`.
  - Delta đúng $+0.01$ $\to$ `0.01`, delta đúng $-0.01$ $\to$ `-0.01`.
- **Phạm vi áp dụng nhất quán giữa Backend và Frontend**:
  1. `session_total_score` và `session_average_score` (buổi phỏng vấn).
  2. Điểm đánh giá từng câu hỏi (`technical_accuracy`, `completeness`, `reasoning_clarity`, `relevance`, `practical_example`, `total_score`).
  3. Xu hướng tiến độ (`InterviewProgressTrendItem.total_score`, `average_score`).
  4. Sai phân so sánh (`InterviewProgressDelta.total_score_delta`, `average_score_delta`).
  5. Điểm số và delta theo nhóm kỹ năng (`CategoryProgressItem`: `first_score`, `previous_score`, `latest_score`, `latest_vs_previous_delta`, `latest_vs_first_delta`).
- **Thiết kế helper tập trung**:
  - **Backend (`backend/app/core/rounding.py`)**:
    - Dùng module chuẩn `decimal.Decimal` với `ROUND_HALF_UP`.
    - `to_decimal`: từ chối an toàn `NaN` và `Infinity` (raise `ValueError`).
    - `round_score`: làm tròn điểm 2 chữ số thập phân.
    - `round_average_score`: chia `total / count` trong không gian `Decimal` trước khi quantize.
    - `round_delta`: trừ `current - base` trong không gian `Decimal` trước khi quantize.
    - Không chuyển `Decimal` về `float` trước khi hoàn tất phép tính.
  - **Frontend (`frontend/app/types/progress.ts`)**:
    - `toRoundedCents`: chuyển đổi số thực thành số nguyên cents an toàn bằng chuỗi cố định định dạng `toFixed(6)` để tránh sai số nhị phân.
    - `round2`: trả về số thực 2 chữ số từ integer cents.
    - `isSameRounded2`: so sánh bình đẳng tuyệt đối theo cùng đơn vị integer cents.
    - `roundAverage2`: tính trung bình và làm tròn `ROUND_HALF_UP` khớp 100% với backend `Decimal`.
    - `roundDelta2`: tính hiệu số giữa hai mốc điểm bằng phép trừ integer cents an toàn.
    - Loại bỏ hoàn toàn epsilon tùy tiện (`Number.EPSILON`) và helper thừa không sử dụng (`isDifferenceAtLeast001`).

## Task 09D - Loại bỏ Float Accumulation trước Decimal Rounding
- **Vấn đề tiềm ẩn của Float Accumulation**:
  - Khi cộng dồn các số thực nhị phân IEEE-754 trước khi ép sang `Decimal` (ví dụ `sum(scores)` hoặc `tech + comp + ...`), sai số tích lũy nhị phân sẽ phát sinh ngay trong phép cộng.
  - Ví dụ thực tế chứng minh sai sót:
    - Xét danh sách điểm `scores = [0.01, 0.06]`.
    - Phép cộng float `0.01 + 0.06` sinh ra `0.06999999999999999`.
    - Nếu lấy kết quả này đưa vào `Decimal(str(sum(...)))` rồi chia 2: `Decimal("0.06999999999999999") / Decimal("2") = Decimal("0.034999999999999995")`.
    - Khi làm tròn `ROUND_HALF_UP`, kết quả bị thụt xuống **`0.03`** (SAI LỆCH).
    - Ngược lại, nếu chuyển từng giá trị sang `Decimal` trước khi cộng: `to_decimal(0.01) + to_decimal(0.06) = Decimal("0.07")`.
    - Phép chia trong không gian Decimal: `Decimal("0.07") / Decimal("2") = Decimal("0.035")`.
    - Khi làm tròn `ROUND_HALF_UP` 2 chữ số, kết quả chính xác tuyệt đối là **`0.04`**.
- **Chuỗi tính toán chuẩn (Standard Calculation Pipeline)**:
  - `convert each value to Decimal` $\to$ `Decimal aggregation` $\to$ `Decimal division (nếu tính trung bình)` $\to$ `quantize ROUND_HALF_UP` $\to$ `float chỉ tại ORM / response boundary`.
- **Nguyên tắc kỹ thuật**:
  1. **Zero built-in `sum()` trên float list**: Tuyệt đối không dùng `sum()` trực tiếp trên danh sách float cho bất kỳ phép tính điểm số nghiệp vụ nào (tổng 5 tiêu chí câu hỏi, tổng điểm 10 câu, trung bình phiên, trung bình category).
  2. **Decimal aggregation helpers tập trung (`backend/app/core/rounding.py`)**:
     - `sum_decimal(values: Iterable)`: chuyển từng phần tử bằng `to_decimal`, khởi tạo tổng bằng `Decimal("0")`, từ chối iterable rỗng, từ chối `NaN`/`Infinity`. Hỗ trợ generator duyệt 1 lần (single-pass).
     - `round_sum_scores(values: Iterable) -> float`: tích lũy trong không gian Decimal rồi quantize `ROUND_HALF_UP`.
     - `round_average_values(values: Iterable) -> float`: duyệt single-pass tính tổng Decimal và đếm số lượng, thực hiện phép chia Decimal trước khi quantize `ROUND_HALF_UP`.
  3. **Frontend Integer Cents Consistency (`frontend/app/types/progress.ts`)**:
     - Bổ sung helper `roundAverageScores(scores: number[])`: tích lũy `toRoundedCents(score)` thành tổng số nguyên cents trước khi chia và làm tròn `ROUND_HALF_UP`, đảm bảo kết quả ở frontend khớp 100% với backend.

## Task 11 - Đóng gói, Cấu hình và Chuẩn bị Triển khai (Docker & Production Hardening)
- **Mục tiêu**:
  - Chuẩn hóa môi trường Development và Production-like.
  - Đóng gói toàn bộ ứng dụng bằng Docker Compose (`docker-compose.prod.yml`) bảo toàn tính độc lập với môi trường dev.
  - Thực thi các nguyên tắc bảo mật: Non-root containers, Fail-fast configuration, Zero-secret leakage, Data persistence.
- **Phân tách môi trường (Environment Separation)**:
  - `APP_ENV`: `development` | `production`.
  - Trong `production`:
    - `DEBUG` bị cấm bật (`DEBUG=False` bắt buộc).
    - `FRONTEND_ORIGINS` bắt buộc phải được khai báo cụ thể; nghiêm cấm wildcard `*`.
    - Production chỉ chấp nhận `AI_PROVIDER=groq` hoặc `AI_PROVIDER=gemini`; fake provider không thể là fallback production.
    - API key tương ứng (`GROQ_API_KEY` hoặc `GEMINI_API_KEY`) và `POSTGRES_PASSWORD` phải là giá trị thật; placeholder bị từ chối fail-fast.
    - Mọi lỗi cấu hình đều `fail-fast` ngay khi khởi tạo ứng dụng với thông điệp rõ ràng, không làm rò rỉ secret vào log/exception.
- **Kiến trúc Docker Containers**:
  - **Backend Image (`backend/Dockerfile`)**:
    - Base `python:3.11.14-slim-bookworm`, user không phải root (`appuser:appgroup`, UID 10001).
    - Layer cache: copy và cài đặt `requirements.txt` trước khi copy mã nguồn.
    - Entrypoint script `entrypoint.sh` thực thi `alembic upgrade head` fail-fast trước khi chuyển quyền điều khiển qua `exec uvicorn` (đảm bảo tín hiệu SIGTERM/SIGINT cho graceful shutdown).
    - Healthcheck endpoint `/api/v1/health`.
  - **Frontend Image (`frontend/Dockerfile`)**:
    - Multi-stage build (deps -> builder -> runner) với `node:20.19.5-alpine3.22`.
    - Sử dụng Next.js standalone output (`output: "standalone"`), chỉ chứa artifact thực thi cần thiết.
    - Chạy dưới user không phải root (`nextjs:nodejs`, UID 10001).
    - Healthcheck HTTP qua `wget` đến trang `/`.
  - **Production Compose Stack (`docker-compose.prod.yml`)**:
    - 3 services: `postgres` (postgres:15-alpine, internal network, không public port ra host), `backend`, `frontend`.
    - Persistent named volumes: `interview_prod_postgres_data` (lưu trữ DB) và `interview_prod_cv_uploads` (lưu trữ file CV).
    - Khởi động tuần tự có điều kiện (`service_healthy`): `postgres` -> `backend` -> `frontend`.
- **Bảo mật và Logging**:
  - `SensitiveDataFilter` tự động che giấu (redact) các chuỗi nhạy cảm như `gsk_...`, `Bearer ...`, `password=...`, `postgresql://...` khỏi tất cả log stream.
  - `HealthCheckFilter` lọc bỏ các request healthcheck định kỳ khỏi access log để tránh ngập lụt log.
  - Global unhandled exception handler ngăn chặn việc lộ traceback hoặc cấu trúc SQL nội bộ ra ngoài client.
- **Tính bền vững dữ liệu (Persistence Guarantees)**:
  - Khởi động lại `backend` hoặc `postgres` container không làm mất bản ghi DB hoặc file vật lý trên volume.
  - Persistence test theo dõi cả UUID và `storage_key`, xóa đúng row/file trong `finally` và dùng sentinel để phát hiện cleanup vượt phạm vi.
  - `docker compose down` giữ nguyên volumes; chỉ `docker compose down -v` mới xóa volume và dữ liệu (destructive action).


