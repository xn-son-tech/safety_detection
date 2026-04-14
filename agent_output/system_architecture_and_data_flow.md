# Kiến Trúc Hệ Thống & Luồng Dữ Liệu (System Architecture & Package Flow)

Tài liệu này cung cấp cái nhìn tổng quan về kiến trúc của hệ thống Safety Detection, phân tích chuyên sâu vào hai thành phần cốt lõi: `backend` và `core_detection`, cũng như cách thức luồng dữ liệu (Data/Package Flow) di chuyển giữa các cấu phần để thực hiện nghiệp vụ nhận diện an toàn lao động.

---

## 1. Hệ Thống Backend (C# .NET Core)

Được xây dựng trên nền tảng .NET Core theo kiến trúc Module, đóng vai trò lưu trữ thông tin, quản lý thiết bị và cung cấp giao diện tương tác cho người quản trị. Hệ thống bao gồm 3 Package chính:

### a. `SafetyDetection.Shared` (Core Logic & Data Models)
Chứa `SafetyDbContext` (Entity Framework Core) và tệp tin siêu dữ liệu `Entities.cs` với các Models:
- **Hạ tầng quản lý**: `Site` (Công trường), `Zone` (Khu vực), `Camera`, `ModelVersion`, `ProcessingRun`.
- **Luật giám sát**: `SafetyCriterion` (Tiêu chí an toàn), `RuleDefinition` (Định nghĩa luật, version tracking), `CameraCriterionAssignment`.
- **Dữ liệu AI (Telemetry & Insight)**: `Detection` (Kết quả nhận diện Realtime), `Violation` (Vi phạm), `ViolationEvidence` (Ảnh vi phạm, toạ độ Bounding Box), `RuleEvaluation` (Kết quả đánh giá theo khung), `FramePreprocessingLog` (Log dữ liệu Preprocessing như SSIM/Laplacian Variance).

### b. `SafetyDetection.Api` (RESTful API Layer)
- Cung cấp các Controller public API như `SitesController`, `ViolationsController`.
- Chịu trách nhiệm nhận dữ liệu đẩy về từ Engine AI trực tiếp hoặc qua Http Client, và Insert an toàn vào DB thông qua Shared DbContext.

### c. `SafetyDetection.Manager` (WinForms Dashboard)
- Ứng dụng Window thực thi tác vụ UI hiển thị cho Admin, lấy/render dữ liệu realtime (bảng lỗi, cấu hình cam). Nơi phân tích dashboard trực quan (`Form1.cs`).

---

## 2. Hệ Thống AI Core Detection (Python)

Đây là khối não bộ ("Computer Vision Engine") phân tích luồng hình ảnh khổng lồ, được viết bằng cấu trúc Python OOP và tận dụng framework YOLOv8, đặt tại thư mục `src/ai_helmet_detection`. Được module hoá rất rõ ràng:

- **`preprocessing` (Tiền xử lý)**: Sử dụng các thuật toán như SSIM (Structural Similarity Index) độ tương đồng so với frame cũ, và CLAHE kết hợp Laplacian Variance (Đo độ mờ). Nếu hình ảnh có chất lượng thấp, frame lập tức bị Drop để giữ tối đa tài nguyên inference của CPU/GPU.
- **`tracking`**: Module bao bọc bên trên Yolo Tracker (`botsort.yaml`) nhúng trong thư viện `YoloWorkerTracker`, giúp bám sát mục tiêu và cấp nhãn `track_id` độc nhất theo thời gian.
- **`rule_engine` & `alert_validation` (Xử lý nghiệp vụ an toàn)**:
  - **Không gian**: Ước lượng vùng nhận diện đầu (Head ROI) thông qua tỷ lệ hộp giới hạn (Bounding Box) của Body (person bbox). Tính toán chỉ số IoU (Intersection over Union) giữa Head ROI và Helmet Detections để xác nhận đó là mũ đang đội trên đầu thay vì đang cầm ở tay hay dán đằng sau balo.
  - **Thời gian**: Tracking qua chuỗi cửa sổ khung hình (Window Frame). Ví dụ: Một ID Tracking buộc phải bị AI phán quyết là đang KHÔNG đội mũ 24 lần liên tiếp (hoặc gián đoạn) trong cửa sổ 30 frames gần nhất thì hệ thống mới nâng cấp nó thành cảnh báo thực tế (`OfficialAlert`).

---

## 3. Package Data Flow (Sơ đồ Dòng chảy Dữ liệu)

Dưới đây là một sơ đồ mô tả luồng khung hình từ khi sinh ra từ Camera đến khi vi phạm xuất hiện lên Dashboard.

> [!NOTE]
> Flow này mô tả vòng đời (Lifecycle) từ khâu Extract RTSP tại Core Detection Model đến tầng View của Manager Application.

```mermaid
graph TD
    %% Định nghĩa các Style cho dễ nhìn
    classDef Csharp fill:#178600,stroke:#0f5800,stroke-width:2px,color:white;
    classDef Python fill:#306998,stroke:#245479,stroke-width:2px,color:white;
    classDef Client fill:#f9f9f9,stroke:#333,stroke-width:2px;

    A[Thiết Bị Camera - RTSP Stream]:::Client --> B[core_detection: FramePreprocessor]:::Python
    
    B -->|SSIM cao / Độ mờ Laplacian| DROP[Bỏ qua Frame/Drop]
    B -->|Accepted Frame| C[core_detection: Object Tracker / YOLOv8]:::Python
    
    C -->|Frame Data + Track ID| D[core_detection: HelmetSystem / Rule Engine]:::Python
    
    %% Bên trong AI Rules
    D -->|Phân tích Không Gian| E[Calculate IoU & Head ROI]:::Python
    E -->|Xác nhận Mất an toàn| F[core_detection: Temporal Validation]:::Python
    
    %% Logic Phân tích Thời không
    F -->|Tracking Window (VD: 24/30 frames)| G{Đủ điều kiện Vi phạm?}
    G -->|Không| H[Giữ trong Cache chờ Update Tương Lai]
    G -->|Có| I[Sinh ra Cảnh Báo - OfficialAlert]:::Python
    
    %% Đẩy sang Backend
    I -. HTTP POST .-> J[backend: SafetyDetection.Api]:::Csharp
    
    J --> K[Entity Framework Core - Data Context]:::Csharp
    K --> L[(Database - SQL Server/Postgres)]
    
    %% Winapps Connect
    L --> M[backend: SafetyDetection.Manager UI]:::Csharp
    M --> User((Người Quản Trị Hệ Thống))
```

### Các Bước Cụ Thể Trong Data Flow:
1. **Thu nhận**: Luồng RTSP truyền liên tục frame về `core_detection` tại `WorkerSafetyPipeline`.
2. **Loại bỏ nhiễu**: `FramePreprocessor` đảm bảo những frame nhiễu động, mờ căm sẽ không tiêu tốn GPU vô ích. 
3. **Phát hiện & Theo dõi**: YOLOv8 quét hình ảnh ra list `Detection` và `TrackedPerson`.
4. **Kiểm tra chéo (Rule Engine)**: Frame hợp lệ cùng Bounding Box được đưa vào phân tích tỉ lệ cắt chéo mũ - đầu.
5. **Chứng nhận (Validation)**: `TrackViolationValidator` xác nhận qua thời gian tránh các yếu tố False Positive (Bóng nháy).
7. **Thông tin**: `SafetyDetection.Manager` có thể Fetch danh sách `Violations`/`Detections` từ Database để hiển thị đồ thị và thông báo Flash cho admin.

---

## 4. Live Video Input - Function Call Flow (Luồng Gọi Hàm Chi Tiết)

Khi hệ thống nhận một luồng Live Video (RTSP/Webcam/Video stream), tiến trình chính sẽ được kích hoạt thông qua pipeline. Chuỗi các hàm (functions) sẽ được gọi liên tục trên từng khung hình (frame) như sau:

1. **Khởi tạo Video:** _(Thực thi tại `pipeline/helmet_pipeline.py`)_
   - Thuộc pipeline `WorkerSafetyPipeline.run()`. Hệ thống gọi `cv2.VideoCapture(source)` để kết nối với nguồn video stream. Lấy thông số FPS và Source Time.
2. **Vòng lặp lấy khung hình (Stream Reading):** _(Thực thi tại `pipeline/helmet_pipeline.py`)_
   - Vòng lặp `while True:` được duy trì trong hàm `run()`, mỗi chu kỳ gọi hàm `capture.read()` để bóc tách 1 `frame`.
3. **Tiền xử lý (Preprocessing):** _(Thực thi tại `preprocessing/preprocessor.py`)_
   - Gọi **`self.preprocessor.process_frame(frame, previous_frame)`** (class `FramePreprocessor`):
     - Tự động chạy thuật toán ảnh (ví dụ CLAHE) trên frame này.
     - Tính toán **Laplacian Variance** (độ đo nhiễu/mờ).
     - So sánh cấu trúc ảnh **SSIM** với `previous_frame`.
   - Hàm trả về biến `accepted` (True/False) quyết định sự sống còn của frame.
4. **Xử lý AI và Nghiệp vụ (nếu `accepted == True`):** 
   - **4.1 Box Tracking:** _(Thực thi tại `tracking/tracker.py`)_ 
     - Gọi **`self.tracker.track_frame(...)`**. Class `YoloWorkerTracker` gọi mô hình YOLO (với Tracker BoT-SORT) thực thi Box Detection, trả về toạ độ Bounding Box và cấp tự động `track_id`.
   - **4.2 Rule Engine (Luật không gian):** _(Thực thi tại `rule_engine/helmet_violation.py`)_
     - Gửi kết quả cho **`validate_helmet_violations_from_results(...)`**. Bên dưới nó sẽ gọi:
       - `build_head_roi(...)`: Nội suy vùng đầu (Head ROI).
       - `calculate_overlap_ratio(...)`: So sánh độ phủ (IoU) giữa cái mũ tìm được và vùng đầu. Trả về mảng `violations` (vi phạm chớp nhoáng của khung hình hiện tại).
   - **4.3 Temporal Validation (Luật thời gian):** _(Thực thi tại `alert_validation/track_violation_validator.py`)_
     - Gọi **`self.validator.update(..., violations, ...)`**. Tại đây class `TrackViolationValidator` đếm số hits vi phạm trên mỗi `track_id`. Nếu số % frame vi phạm trong window vượt ngưỡng yêu cầu => Cấp cảnh báo đỏ **`official_alerts`**.
   - **4.4 Đồ họa (Annotation):** _(Thực thi tại `pipeline/helmet_pipeline.py`)_
     - Gọi hàm đồ họa **`self._annotate_frame(...)`**. OpenCV sẽ vẽ khung viền (bbox) và ghim các metrics chữ (như SSIM, trạng thái "ACCEPTED") ngay trên frame hiển thị.
5. **Đóng gói Frame Pipeline:** _(Thực thi tại `pipeline/helmet_pipeline.py`)_
   - Hàm **`yield PipelineFrame(...)`** trả ra một Object kiện toàn chứa toàn bộ tham số Tracking, Violations, Metrics, và Annotated Frame do class dataclass `PipelineFrame` định nghĩa.
6. **Lưu vết và Bắn API (Outbound API Call):** _(Phụ thuộc vào Script Consumer/Runner)_
   - Ở vòng lặp của Caller (nơi gọi hàm `run()`), hệ thống quét đọc mảng `official_alerts`. Cấu phần này thường dùng Async hoặc HTTP Client để truyền Data Payload và Evidence Image chứa `base64` hay URL vật lý sang `backend/SafetyDetection.Api` ghi nhận.
