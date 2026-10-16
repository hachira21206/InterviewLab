# Hướng dẫn Môi trường và Dọn dẹp

## 1. Môi trường Backend (Python)
- Toàn bộ dependency được cài đặt vào `backend/.venv` thông qua `bootstrap.ps1`.
- Trình quản lý gói `pip` được cấu hình để lưu cache tại `.cache/pip` ở thư mục gốc của dự án.
- Không có package nào được cài đặt ở cấp độ global hay user site.
- Để làm sạch hoàn toàn môi trường Python, bạn có thể xóa thư mục `backend/.venv` và thư mục `.cache/pip`.

## 2. Môi trường Frontend (Node.js)
- Dependency của frontend được lưu tại `frontend/node_modules`.
- Trình quản lý gói `npm` được cấu hình để lưu cache tại `.cache/npm` ở thư mục gốc của dự án.
- Không sử dụng các công cụ tải package ngoài mà không có sự kiểm soát.
- Để làm sạch môi trường Node.js, bạn có thể xóa thư mục `frontend/node_modules` và `.cache/npm`.

## 3. Storage và Dữ liệu người dùng (Upload CV)
- Ứng dụng lưu các CV được tải lên tại thư mục `data/uploads/cv`.
- Cơ chế quản lý file đảm bảo **triệt để không có file mồ côi (orphan file)**:
  - Nếu kết nối DB bị lỗi (DB commit/flush failure), file vật lý sẽ lập tức bị hệ thống xóa đi.
  - Các file test từ backend unit tests được tạo thông qua pytest's `tmp_path`, vì vậy sẽ tự động bị xóa bởi pytest sau khi chạy xong.
  - Các script E2E/Playwright sử dụng các test có gắn marker và được thiết kế để tự xóa khỏi database và filesystem ở block `finally`.
- **Lưu ý quan trọng**: CV là dữ liệu người dùng. Khi hoàn tất đồ án hoặc muốn dọn dẹp sạch sẽ, bạn có thể xóa toàn bộ thư mục `data/uploads/cv` (giữ lại file `.gitkeep`). Không nên commit các file trong thư mục này lên git.

## 4. Playwright & Test Môi trường UI
- Môi trường giả lập UI được cài tại thư mục `.scratch/.venv`. Script có thể cài đặt độc lập với dự án thông qua `.scratch/requirements.txt`.
- Các browser Playwright tải về thường nằm ở `AppData\Local\ms-playwright`. Bạn có thể giữ lại nếu dùng cho các dự án khác, hoặc chạy `playwright uninstall` trước khi xóa.

## 5. Dữ liệu Cơ sở dữ liệu và Khóa ngoại Cascade (Tasks 01 - 09)
Hệ thống gồm 8 bảng với quan hệ cascade (Task 09 không thêm bảng mới mà tổng hợp trực tiếp từ dữ liệu hiện có):
1. `cv_documents`
2. `job_applications` (FK `cv_document_id` ON DELETE CASCADE)
3. `application_analyses` (FK `job_application_id` ON DELETE CASCADE)
4. `interview_sessions` (FK `job_application_id` ON DELETE CASCADE, quan hệ 1-N từ Task 08)
5. `interview_questions` (FK `interview_session_id` ON DELETE CASCADE)
6. `interview_responses` (FK `interview_session_id` ON DELETE CASCADE, FK `interview_question_id` ON DELETE CASCADE)
7. `interview_evaluations` (FK `interview_session_id` ON DELETE CASCADE)
8. `interview_response_evaluations` (FK `interview_evaluation_id` ON DELETE CASCADE, FK `interview_response_id` ON DELETE CASCADE)

Khi xóa 1 `cv_documents` hoặc 1 `job_applications`, toàn bộ các attempt phỏng vấn, câu hỏi, câu trả lời và đánh giá AI liên quan sẽ được tự động cascade sạch sẽ, đảm bảo trạng thái zero-orphan. Test isolation được bảo vệ bằng cơ chế cleanup theo ID cụ thể và sentinel record xác thực tính cô lập. Toàn bộ các phép tính so sánh tiến độ của Task 09 truy vấn an toàn và không tạo thêm bản ghi rác nào.

## 6. Cấu hình AI Provider và Bảo mật Thông tin
- Chọn một provider trong `.env`: `AI_PROVIDER=groq` kèm `GROQ_API_KEY=gsk_...`, hoặc `AI_PROVIDER=gemini` kèm `GEMINI_API_KEY=AIza_...`. Không commit file `.env` hoặc API key.
- Gemini Free tier phù hợp để demo nhưng vẫn có giới hạn request/token; lỗi quota được backend chuẩn hóa thành `RATE_LIMITED` và không làm hỏng trạng thái phỏng vấn.
- Mọi automated test mặc định sử dụng `FakeAnalysisProvider` hoặc mock route Playwright để không tiêu tốn quota và chạy hoàn toàn offline / deterministic.
- Thông tin nhạy cảm (Email, Số điện thoại, Secret Tokens) được tự động gỡ bỏ qua hàm `redact_sensitive_info` trước khi gửi đến external AI.

## 7. Môi trường Production-like với Docker Compose (Task 11)
- **Tập tin Compose**: `docker-compose.prod.yml` độc lập hoàn toàn với `docker-compose.yml` (dev).
- **Tên project và volume**:
  - Project name: `interview_prod`.
  - Database volume: `interview_prod_postgres_data`.
  - Upload storage volume: `interview_prod_cv_uploads`.
- **Cơ chế khởi động an toàn**:
  - `postgres` (healthcheck qua `pg_isready`).
  - `backend` (đợi postgres healthy, tự động chạy `alembic upgrade head` fail-fast, sau đó uvicorn lắng nghe port 8000).
  - `frontend` (đợi backend healthy, Next.js standalone phục vụ port 3000).

## 8. Hướng dẫn Sao lưu và Phục hồi Dữ liệu Production
- **Sao lưu (Backup)**:
  ```powershell
  docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U postgres -d interview_db > backup_prod.sql
  ```
- **Phục hồi (Restore)**:
  ```powershell
  cat backup_prod.sql | docker compose -f docker-compose.prod.yml exec -T postgres psql -U postgres -d interview_db
  ```

## 9. Nguyên tắc Dọn dẹp và Cảnh báo Xóa Dữ liệu (Destructive Warnings)
- **Dọn dẹp an toàn (Bảo toàn dữ liệu)**:
  ```powershell
  docker compose -f docker-compose.prod.yml down
  ```
  Lệnh này gỡ bỏ container và network, nhưng **bảo toàn nguyên vẹn 100% volumes** `postgres_data` và `cv_uploads`.
- **Dọn dẹp hủy diệt (Destructive - Xóa toàn bộ Volume)**:
  > [!CAUTION]
  > Lệnh `docker compose down -v` hoặc `docker compose -f docker-compose.prod.yml down -v` sẽ **XÓA TOÀN BỘ VĨNH VIỄN** volumes dữ liệu người dùng và cơ sở dữ liệu. Tuyệt đối không chạy lệnh này nếu chưa sao lưu!
- **Các thư mục cache cục bộ có thể xóa an toàn khi cần giải phóng dung lượng**:
  - `.cache/pip/`
  - `.cache/npm/`
  - `frontend/.next/`
  - `backend/.pytest_cache/`
  - `backend/__pycache__/`
  - Tuyệt đối không xóa `data/uploads/cv/.gitkeep`.

