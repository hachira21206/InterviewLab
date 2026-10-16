# Dự án luyện phỏng vấn ảo theo CV và vị trí ứng tuyển

## 1. Mục đích tài liệu

Tài liệu này lưu lại các quyết định đã thống nhất trước khi bắt đầu xây dựng dự án. Nội dung được dùng làm mốc tham chiếu khi phân tích yêu cầu, thiết kế hệ thống, lập trình và kiểm thử.

Ngày cập nhật: 08/10/2026

## 2. Tổng quan dự án

Tên dự kiến của đồ án:

**Ứng dụng web luyện phỏng vấn ảo theo CV và vị trí ứng tuyển**

Ứng dụng hỗ trợ sinh viên và ứng viên Intern luyện phỏng vấn IT. Hệ thống đọc CV, phân tích mô tả công việc, xây dựng kế hoạch phỏng vấn, đặt câu hỏi thích ứng và tạo báo cáo giúp ứng viên cải thiện.

Đây là đồ án học tập. Mục tiêu chính là xây dựng được một quy trình hoàn chỉnh, có thể giải thích rõ cơ chế hoạt động và chứng minh bằng các trường hợp kiểm thử.

## 3. Các quyết định đã chốt

### 3.1 Đối tượng sử dụng

- Sinh viên và ứng viên Intern.
- Chưa hướng đến ứng viên Middle, Senior hoặc nhà tuyển dụng chuyên nghiệp trong MVP.
- Người dùng chính là ứng viên tự luyện phỏng vấn.

### 3.2 Phạm vi nghề nghiệp

- Phạm vi ban đầu là ngành IT.
- Vị trí được tập trung trong MVP là **Backend Developer Intern**.
- Không bắt người dùng chọn riêng Python, Java, Node.js hoặc một ngôn ngữ backend cụ thể.
- Hệ thống kiểm tra kiến thức Backend chung và điều chỉnh câu hỏi theo công nghệ xuất hiện trong CV hoặc mô tả công việc.

### 3.3 Ngôn ngữ

- CV đầu vào có thể bằng tiếng Việt hoặc tiếng Anh.
- CV có thể chứa đồng thời tiếng Việt và thuật ngữ kỹ thuật tiếng Anh.
- Câu hỏi phỏng vấn được trình bày bằng tiếng Việt.
- Người dùng trả lời bằng tiếng Việt và có thể sử dụng thuật ngữ kỹ thuật tiếng Anh.
- Báo cáo đánh giá được viết bằng tiếng Việt dễ hiểu.

### 3.4 Nền tảng

- Sản phẩm được xây dựng dưới dạng ứng dụng web.
- Chưa xây dựng ứng dụng mobile trong MVP.
- Phỏng vấn bằng văn bản trong phiên bản đầu tiên.
- Voice, video và phân tích biểu cảm được để ngoài phạm vi MVP.

## 4. Bài toán cần giải quyết

Sinh viên và ứng viên Intern thường chưa biết nhà tuyển dụng có thể hỏi gì từ CV, dự án cá nhân và yêu cầu của vị trí ứng tuyển. Các bộ câu hỏi có sẵn thường chung chung, không thay đổi theo hồ sơ hoặc câu trả lời của từng ứng viên.

Ứng dụng cần giải quyết các vấn đề sau:

- Tạo câu hỏi dựa trên nội dung thật trong CV.
- Kết hợp câu hỏi từ yêu cầu của vị trí ứng tuyển.
- Kiểm tra kiến thức Backend nền tảng phù hợp với cấp độ Intern.
- Đặt câu hỏi đào sâu khi câu trả lời còn thiếu hoặc chung chung.
- Đánh giá câu trả lời bằng tiêu chí rõ ràng và có bằng chứng.
- Chỉ ra kiến thức người dùng cần cải thiện sau buổi phỏng vấn.

## 5. Luồng hoạt động chính

1. Người dùng đăng ký hoặc đăng nhập.
2. Người dùng tải CV định dạng PDF hoặc DOCX.
3. Hệ thống đọc và trích xuất thông tin từ CV.
4. Người dùng kiểm tra, sửa và xác nhận thông tin đã trích xuất.
5. Người dùng chọn vị trí Backend Developer Intern và nhập mô tả công việc.
6. Hệ thống phân tích sự liên quan giữa CV và mô tả công việc.
7. Hệ thống lập kế hoạch phỏng vấn và chọn các năng lực cần kiểm tra.
8. Người dùng thực hiện phỏng vấn bằng văn bản.
9. Hệ thống phân tích từng câu trả lời và quyết định hỏi sâu hoặc chuyển chủ đề.
10. Hệ thống tạo báo cáo cuối buổi.
11. Người dùng xem lại lịch sử và luyện lại những nội dung còn yếu.

## 6. Chức năng MVP

### 6.1 Quản lý tài khoản

- Đăng ký và đăng nhập.
- Quản lý thông tin cơ bản của người dùng.

### 6.2 Quản lý CV

- Tải CV PDF hoặc DOCX.
- Hỗ trợ CV tiếng Việt và tiếng Anh.
- Trích xuất học vấn, kỹ năng, dự án, kinh nghiệm và chứng chỉ.
- Cho phép người dùng kiểm tra và sửa kết quả trích xuất.
- Không tự suy đoán thông tin không xuất hiện trong CV.

### 6.3 Quản lý vị trí ứng tuyển

- Vị trí chính là Backend Developer Intern.
- Người dùng có thể dán nội dung Job Description, viết tắt là JD.
- JD có thể để trống nếu người dùng chỉ muốn luyện kiến thức Backend Intern chung.
- Chưa nhập JD trực tiếp từ URL trong MVP.

### 6.4 Cấu hình buổi phỏng vấn

- Chọn thời lượng hoặc số lượng câu hỏi.
- Chọn trọng tâm như CV, kiến thức kỹ thuật hoặc cân bằng.
- Hỗ trợ hai định hướng chế độ:
  - Mock Interview: không gợi ý trong lúc phỏng vấn, nhận xét sau khi kết thúc.
  - Coach Mode: có thể nhận gợi ý và phản hồi trong quá trình luyện tập.

Mock Interview là chế độ cần ưu tiên trong MVP. Coach Mode được triển khai nếu tiến độ cho phép.

### 6.5 Thực hiện phỏng vấn

- Mỗi thời điểm hiển thị một câu hỏi.
- Câu hỏi được tạo từ CV, JD và kiến thức Backend nền tảng.
- Hệ thống lưu toàn bộ câu hỏi và câu trả lời.
- Hệ thống theo dõi năng lực nào đã được kiểm tra.
- Mỗi chủ đề chỉ được hỏi sâu một số lần giới hạn.
- Hệ thống tránh lặp lại câu hỏi và tránh hỏi quá khó so với cấp độ Intern.

### 6.6 Báo cáo cuối buổi

- Điểm theo từng nhóm năng lực đã được kiểm tra.
- Điểm mạnh của ứng viên.
- Nội dung còn thiếu hoặc chưa rõ.
- Trích dẫn từ câu trả lời làm bằng chứng.
- Gợi ý cách trả lời tốt hơn.
- Danh sách kiến thức nên ôn tập.
- Danh sách câu hỏi nên luyện lại.
- Ghi rõ nhóm năng lực chưa được kiểm tra thay vì tự động cho điểm.

## 7. Năng lực Backend Intern cần kiểm tra

### 7.1 Lập trình nền tảng

- Biến, kiểu dữ liệu và hàm.
- Class và object.
- Collection hoặc cấu trúc dữ liệu cơ bản.
- Exception handling.
- Async và await khi CV hoặc JD có yêu cầu.
- Cách tổ chức mã nguồn.

### 7.2 Backend và REST API

- Client và server.
- Request và response.
- Các HTTP method thường dùng.
- HTTP status code.
- Validation dữ liệu.
- Error handling.
- Authentication và authorization.
- Phân trang, tìm kiếm và lọc dữ liệu.
- Cách tổ chức một dự án backend.

### 7.3 Cơ sở dữ liệu

- Bảng, cột và kiểu dữ liệu.
- Primary key và foreign key.
- Quan hệ giữa các bảng.
- CRUD và JOIN.
- Index ở mức cơ bản.
- Transaction ở mức khái niệm.
- Sự khác nhau giữa ORM và SQL.

### 7.4 Dự án trong CV

- Vai trò thật của ứng viên.
- Lý do chọn công nghệ.
- Luồng dữ liệu của hệ thống.
- Khó khăn và cách xử lý.
- Cách tìm và sửa lỗi.
- Hạn chế của dự án.
- Điều ứng viên muốn cải thiện nếu làm lại.

### 7.5 Testing và debugging

- Unit test và integration test ở mức cơ bản.
- Kiểm thử API bằng công cụ như Postman.
- Cách đọc lỗi và log.
- Quy trình xác định nguyên nhân khi API hoặc dữ liệu gặp lỗi.

### 7.6 Git và làm việc nhóm

- Commit, branch, merge và pull request.
- Xử lý xung đột mã nguồn ở mức cơ bản.
- Cách trao đổi khi không hiểu yêu cầu hoặc gặp vấn đề.

### 7.7 Bảo mật và triển khai cơ bản

- Không lưu mật khẩu ở dạng văn bản thường.
- Mục đích của token.
- Biến môi trường và secret.
- Không đưa mật khẩu hoặc khóa API lên Git.
- Docker ở mức cơ bản nếu CV hoặc JD đề cập.

## 8. Nguyên tắc tạo câu hỏi

Hệ thống sử dụng ba nguồn câu hỏi:

- CV-based: câu hỏi dựa trên kỹ năng và dự án trong CV.
- JD-based: câu hỏi dựa trên yêu cầu của vị trí ứng tuyển.
- Core-based: câu hỏi Backend Intern nền tảng.

CV không nhắc đến một kỹ năng không có nghĩa là ứng viên không biết kỹ năng đó. Hệ thống chỉ đánh dấu là chưa có bằng chứng và đặt câu hỏi để kiểm tra, không tự động trừ điểm.

Mỗi câu hỏi cần lưu được:

- Năng lực đang kiểm tra.
- Nguồn tạo câu hỏi.
- Mức độ khó.
- Nội dung kiến thức mong đợi.
- Điều kiện cần hỏi sâu.
- Số lần hỏi sâu tối đa.

## 9. Nguyên tắc đánh giá

Mỗi câu trả lời được xem xét theo các tiêu chí:

- Correctness: mức độ đúng về kiến thức.
- Relevance: mức độ trả lời đúng trọng tâm.
- Evidence: ví dụ hoặc bằng chứng từ dự án và kinh nghiệm.
- Clarity: mức độ rõ ràng và có cấu trúc.

Mỗi nhận xét cần chỉ ra bằng chứng từ câu trả lời. Hệ thống không chỉ trả về một điểm số mà không giải thích.

Kết quả được trình bày là đánh giá có AI hỗ trợ, không phải kết luận tuyệt đối về năng lực hoặc khả năng được tuyển dụng.

Hệ thống không đánh giá ngoại hình, giọng vùng miền, giới tính, tuổi, trường học hoặc các đặc điểm nhạy cảm khác.

## 10. Kiến trúc định hướng

MVP sử dụng Modular Monolith, nghĩa là triển khai một backend nhưng chia thành các module nghiệp vụ rõ ràng. Chưa sử dụng microservices.

Các module chính dự kiến gồm:

- Authentication.
- CV và JD Processing.
- Candidate Profile.
- Competency và Rubric Bank.
- Interview Planning.
- Interview Engine.
- Question Generation.
- Answer Evaluation.
- Final Report.
- Interview History.

## 11. Công nghệ định hướng

### 11.1 Frontend

- Next.js.
- TypeScript.
- Tailwind CSS.

### 11.2 Backend

- Python.
- FastAPI.
- Pydantic để kiểm tra dữ liệu vào, dữ liệu ra và kết quả từ AI.

### 11.3 Cơ sở dữ liệu

- PostgreSQL.
- SQLAlchemy để làm việc với database.
- Alembic để quản lý migration.

### 11.4 Lưu trữ tài liệu

- S3-compatible storage hoặc một dịch vụ lưu trữ tương đương.
- Không lưu trực tiếp toàn bộ file CV trong bảng database.

### 11.5 Tích hợp AI

- OpenAI Responses API thông qua OpenAI Python SDK.
- Structured Outputs kết hợp với Pydantic hoặc JSON Schema.
- Model cụ thể được cấu hình bằng biến môi trường để có thể thay đổi mà không sửa nghiệp vụ.

### 11.6 Kiểm thử

- Pytest cho backend và Interview Engine.
- Vitest cho frontend nếu cần kiểm thử đơn vị.
- Playwright cho kiểm thử luồng người dùng trên web.

### 11.7 Triển khai

- Docker để đóng gói môi trường chạy.
- Chiến lược hosting cụ thể chưa được chốt.

## 12. Cách AI tham gia vào hệ thống

LLM thực hiện các tác vụ cần hiểu ngôn ngữ:

- Trích xuất thông tin từ CV.
- Phân tích JD.
- Lập kế hoạch phỏng vấn.
- Viết câu hỏi bằng tiếng Việt.
- Phân tích nội dung câu trả lời.
- Đề xuất câu hỏi đào sâu.
- Viết báo cáo cuối buổi.

LLM không được tự kiểm soát toàn bộ buổi phỏng vấn. Interview Engine do ứng dụng lập trình sẽ quyết định:

- Đang kiểm tra năng lực nào.
- Chủ đề nào đã hoàn thành.
- Đã hỏi sâu bao nhiêu lần.
- Khi nào chuyển sang chủ đề mới.
- Khi nào kết thúc buổi phỏng vấn.
- Dữ liệu nào được lưu vào database.

Các prompt dự kiến được tách riêng theo nhiệm vụ:

- CV Extractor.
- JD Analyzer.
- Interview Planner.
- Question Generator.
- Answer Evaluator.
- Final Report Generator.

Mỗi prompt cần có mã phiên bản để phục vụ kiểm thử và truy vết.

## 13. Công nghệ chưa cần trong MVP

- LangChain hoặc framework orchestration phức tạp.
- RAG nếu chưa có kho tài liệu lớn.
- Vector database.
- Fine-tuning mô hình.
- Microservices.
- Redis hoặc hàng đợi tác vụ nếu chưa xuất hiện nhu cầu thực tế.
- Voice, video và phân tích biểu cảm.
- Mobile application.
- Live coding và tự động chạy mã nguồn của ứng viên.
- System design quy mô lớn hoặc kiến thức DevOps chuyên sâu.

Các công nghệ này chỉ được bổ sung khi có yêu cầu cụ thể và đủ thời gian.

## 14. Dữ liệu chính dự kiến

- User.
- CV Document.
- Candidate Profile.
- Job Description.
- Competency.
- Rubric.
- Interview Plan.
- Interview Session.
- Interview Turn.
- Answer Evaluation.
- Final Report.
- Prompt Version.

PostgreSQL là nguồn dữ liệu chính thức của ứng dụng. Không sử dụng bộ nhớ hội thoại của nhà cung cấp AI làm nơi lưu trạng thái duy nhất.

## 15. Bảo mật và quyền riêng tư

- Chỉ cho phép định dạng CV cần thiết như PDF và DOCX.
- Kiểm tra loại file thực tế, không chỉ kiểm tra phần mở rộng.
- Giới hạn dung lượng file.
- Đổi tên file khi lưu trữ.
- Lưu file ngoài thư mục public.
- Chỉ người dùng được cấp quyền mới có thể truy cập CV.
- Cho phép xóa CV và lịch sử phỏng vấn.
- Không đưa thông tin cá nhân không cần thiết vào prompt.
- Không ghi khóa API, mật khẩu hoặc secret vào mã nguồn.

## 16. Tiêu chí hoàn thành MVP

MVP được xem là hoàn thành khi người dùng có thể:

1. Tải một CV thật bằng tiếng Việt hoặc tiếng Anh.
2. Kiểm tra và sửa dữ liệu hệ thống trích xuất.
3. Nhập một JD Backend Developer Intern.
4. Thực hiện trọn vẹn một buổi phỏng vấn bằng văn bản.
5. Nhận câu hỏi bám theo CV, JD và kiến thức Backend nền tảng.
6. Nhận câu hỏi đào sâu phù hợp với câu trả lời trước đó.
7. Nhận báo cáo có điểm, nhận xét, bằng chứng và hướng cải thiện.
8. Xem lại lịch sử buổi phỏng vấn.

## 17. Những điểm chưa chốt

Các nội dung sau cần được quyết định trong giai đoạn thiết kế chi tiết:

- Tên thương mại hoặc tên tiếng Anh của ứng dụng.
- Model AI cụ thể và giới hạn chi phí sử dụng.
- Dịch vụ đăng nhập.
- Dịch vụ object storage.
- Nền tảng triển khai frontend, backend và database.
- Thời lượng và số câu hỏi mặc định của một buổi phỏng vấn.
- Thang điểm chính thức và công thức tính điểm tổng.
- Coach Mode có nằm trong MVP bắt buộc hay không.
- Thời gian lưu CV và lịch sử phỏng vấn.
- Bộ CV, JD và câu trả lời chuẩn dùng để đánh giá chất lượng hệ thống.

## 18. Nguyên tắc kiểm soát phạm vi

Mọi chức năng mới cần trả lời ba câu hỏi trước khi được đưa vào MVP:

1. Chức năng có cần thiết cho luồng tải CV, nhập JD, phỏng vấn và nhận báo cáo không?
2. Chức năng có thể kiểm thử rõ ràng trong phạm vi đồ án không?
3. Chức năng có làm tăng đáng kể thời gian hoặc độ phức tạp nhưng không cải thiện giá trị cốt lõi không?

Nếu chức năng không phục vụ trực tiếp quy trình cốt lõi, chức năng đó được chuyển sang hướng phát triển sau MVP.
