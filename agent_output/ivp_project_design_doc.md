# TÀI LIỆU THIẾT KẾ ĐỒ ÁN: HỆ THỐNG GIÁM SÁT BẢO HỘ LAO ĐỘNG (Hybrid IVP & AI)

*Tài liệu này được thiết kế theo chuẩn đặc tả yêu cầu phần mềm và luận văn học thuật. Điểm nhấn lớn nhất là việc tách bạch và làm nổi bật phần **Xử lý Ảnh và Video truyền thống (IVP)** để hội đồng/giảng viên thấy rõ lượng kiến thức của môn học được áp dụng vào đồ án, thay vì chỉ phụ thuộc vào Deep Learning (YOLO/LLM).*

---

## 1. Phân tích yêu cầu bài toán
### 1.1 Yêu cầu nghiệp vụ (Business Requirements)
*   Hệ thống có khả năng phân tích luồng Video/RTSP Stream từ camera công trường theo thời gian thực.
*   Nhận diện công nhân có mặt trong khung hình nhưng KHÔNG lưu trữ danh tính sinh trắc học để tối ưu chi phí (Chỉ phát sinh Tracking ID).
*   Giám sát và đưa cảnh báo khi phát hiện công nhân thiếu trang thiết bị bảo hộ, trọng tâm MVP là **Mũ bảo hộ (Helmet)**.

### 1.2 Yêu cầu Xử lý Ảnh (IVP Requirements) - *Nền tảng môn học*
*   Phải áp dụng các phép biến đổi không gian màu, phép lọc nhiễu, đạo hàm không gian để tiền xử lý khung hình trước khi đưa vào mô hình học sâu.
*   Video thực tế rung lắc, ánh sáng phức tạp (ngược sáng, lóa sáng) phải được giải quyết bằng thuật toán xử lý ảnh truyền thống.

### 1.3 Yêu cầu phi chức năng (Non-functional)
*   **Performance:** FPS (Frame per second) của toàn bộ pipeline duy trì mức >= 20 FPS trên phần cứng GPU tầm trung.
*   **Độ trễ (Latency):** Dưới 500ms tính từ lúc bắt hình đến khi đẩy cảnh báo về Database.

---

## 2. Thiết kế Pipeline Xử lý (Hybrid Processing Pipeline)
Kiến trúc luồng xử lý lai (Hybrid) kết hợp sức mạnh của thị giác máy tính cổ điển (Classical Computer Vision - IVP) và học sâu (Deep Learning).

### 2.1 Các Giai đoạn (Phases)
1. **Giai đoạn Thu nhận Video (Video Acquisition):** Bắt luồng RTSP camera 1080p, giải mã (decode) H264 thành mảng đa chiều (Tensors).
2. **Giai đoạn Xử lý Ảnh Tín hiệu gốc (Traditional IVP - Đất diễn của nhóm):** Làm mịn ảnh, đo lường tần số không gian đồ (spatial frequency), tăng cường độ tương phản.
3. **Giai đoạn Định vị & Phân loại học sâu (AI Inference):** Trích xuất tọa độ Bounding box của Người và Mũ.
4. **Giai đoạn Hình học Giải tích (Geometric Engine):** Liên kết thực thể Mũ vào Người.

---

## 3. Phân rã Chi tiết các Module Hệ thống

Đây là phần mang đi báo cáo (Present) với TS để chứng minh nhóm làm ra một đồ án Xử lý Ảnh đúng nghĩa.

### 3.1 Module Tiền xử lý Ảnh (Image Pre-processing Module) - *Đất diễn số 1*
Thay vì đẩy ảnh RAW thẳng vào YOLO, nhóm thiết kế một Module dùng các phép biến đổi ma trận để làm sạch ảnh.
*   **a. Biến đổi Không gian Cơ sở (Color Space Transformation):** Chuyển ảnh góc RGB sang hệ màu **HSV (Hue-Saturation-Value)** để bóc tách yếu tố "Độ rọi" (Value). Mũ bảo hộ trên công trường thường bị mặt trời chiếu lóa (trắng xóa). Việc khử/cân chỉnh kênh V (Value) giúp giữ lại màu màu Vàng/Trắng của cấu trúc mũ mà không bị mất nét.
*   **b. Tăng cường Độ tương phản Thích ứng (CLAHE):** Histogram Equalization (HE) truyền thống làm dội nhiễu. Sử dụng thuật toán `CLAHE (Contrast Limited Adaptive Histogram Equalization)` chia ảnh ra các ô `8x8 grid`, tính toán lại biểu đồ tần suất (histogram) cho từng ô cục bộ để xử lý tình huống ngược sáng công trường.
*   **c. Định lượng Biến Thiên Cạnh (Edge Variance Filtering):** Áp dụng hạt nhân (Kernel) theo **toán tử Laplacian** để tính Gradient mép cạnh (Edge gradient). Dựa trên phương sai (Variance) của mảng ma trận Laplacian, nếu nhỏ hơn một ngưỡng Threshold định sẵn -> Đây là frame bị mờ (do camera rung gió hoặc người chạy gấp). Hệ thống drop luôn frame để tiết kiệm 100% tài nguyên chạy YOLO. 

### 3.2 Module Học Sâu (Deep Feature Extraction Module)
*   Sử dụng YOLOv8 làm Backbone. Module này lấy ảnh đã qua làm sạch tại 3.1 để hồi quy Bounding Box tĩnh (Trích xuất các ô chữ nhật chứa Người, Mũ chuẩn, Nón thời trang/No Helmet).
*   Lý do chọn YOLO: Xử lý mạng chập tích phân One-stage, không có Region Proposal (như Faster RCNN) -> Đáp ứng phần cứng cấu hình thấp tại biên Edge.

### 3.3 Module Lai (Hybrid Validation Module) - *Đất diễn số 2*
*   **Tìm kiếm Mũ bằng Hình thái học (Morphological Verification):** Trong các góc phức tạp, nhóm bổ sung một luồng phụ. Cắt lấy ROI (Region của bounding box Person). Áp dụng thuật toán **Canny Edge Detection** để tìm kiếm viền cong bán nguyệt (tố chất hình học của chiếc mũ) để đối chiếu chéo (Cross-check) với kết quả nhận hình dáng của AI. 
*   **Tính toán tỷ lệ khung (Aspect Ratio Heuristic):** Dùng toán học Tỷ lệ Width/Height của hộp bao người (`Aspect_ratio = w / h`). Nếu tỷ lệ dẹt > 1 (Người đang cúi gập), kích hoạt tính toán vùng đỉnh đầu dịch chuyển sang bên mép rìa (X-axis) thay vì nắp dọc (Y-axis). 

---

## 4. Kiến trúc Tổng thể (Overall System Architecture)
Hệ thống là kiến trúc hướng sự kiện thời gian thực (Real-time Event-driven Architecture):

1. **Tầng Edge (Camera & Local Server):** Nơi vận hành trực tiếp bộ OpenCV (Xử lý ảnh cổ điển) và Pytorch (YOLO) để bắt frame, mổ tả hình dáng và tracking ID công nhân.
2. **Tầng Middleware (In-memory Buffer):** Nhận dòng chảy dữ liệu mảng, đếm cửa sổ thời gian (30 frame/giây) dựa trên Time-Sliding Voting. Lọc bỏ các tín hiệu cảnh báo nhấp nháy (Flickering).
3. **Tầng Core Database:** Nơi ghi nhận kết quả lưu trú cho Admin (Metadata hình thái + Link ảnh chụp + Timestamp).
4. **Tầng Application (Dashboard):** Giao diện Web/App kéo dữ liệu từ WebSockets.

---

## 5. Sơ đồ Khối (Block Diagram)

Sơ đồ thể hiện khối liên kết vật lý và thư viện.

```mermaid
block-beta
  columns 3
  
  %% Row 1
  Camera_Hardware("IP Camera (RTSP)")
  space
  Admin_Dashboard("Web/Desktop Dashboard (React/Flet)")
  
  %% Row 2
  down_arrow1<["VLAN / Cable"]>(down)
  space
  up_arrow1<["WebSockets / HTTP API"]>(up)
  
  %% Row 3
  block:DeviceServer:3
      columns 4
      
      block:OpenCV_Module
        title_cv("IVP Module (OpenCV)")
        op1("Color Space(HSV)") 
        op2("Filter (Laplacian)")
        op3("CLAHE (Histogram)")
      end
      
      right_arrow2<["Clean Tensors"]>(right)
      
      block:DL_Module
        title_dl("AI Module (YOLOv8)")
        op4("CNN Feature Layer")
        op5("B-Box Regression")
        op6("BoT-SORT Tracker")
      end

      right_arrow3<["Bboxes + ID"]>(right)
      
      block:Logic_Module
        title_log("Logic & Data")
        op7("Rule Engine")
        op8("Cooldown Buffer")
        op9("Save Metadata to DB")
      end
  end
  
  Camera_Hardware --> DeviceServer
  DeviceServer --> Admin_Dashboard
```

---

## 6. Sơ đồ Thuật toán Vận hành (Operational Flowchart)

Thể hiện lưu đồ ra quyết định trên mỗi một khung hình (Frame) riêng lẻ. Cấu trúc để thiết kế hàm thuật toán (Function scope).

```mermaid
graph TD
    Start((Bắt đầu Frame t)) --> B{Tính phương sai Laplacian}
    
    B -- "< Threshold (Nhòe)" --> C_Drop[Hủy Frame t]
    B -- ">= Threshold (Nét)" --> C[CLAHE & Chuyển không gian màu HSV]
    
    C --> D[YOLOv8 Trích xuất Feature Map]
    D --> E[BoT-SORT: Gắn Tracking ID nhân sự]
    
    E --> F[Truy xuất tọa độ PersonBox & HatBox]
    F --> G{Tính Aspect Ratio của PersonBox}
    
    G -- "Tỷ lệ > 1 (Cúi dọc)" --> H1[Quy hoạch Vùng tìm Đầu trên trục Ngang X]
    G -- "Tỷ lệ <= 1 (Đứng thẳng)" --> H2[Quy hoạch Vùng Top 25% trực dọc Y]
    
    H1 --> I{Có tìm thấy HatBox trong vùng quy hoạch?}
    H2 --> I
    
    I -- "TRUE (Có mũ)" --> J[Ghi nhận Safe ID vào Buffer]
    I -- "FALSE (Thiếu mũ)" --> K[Ghi Vi phạm ID vào Buffer]
    
    K --> L{Trong 30 Frame gần nhất có > 25 lần Vi phạm?}
    
    L -- "Không đủ tỷ lệ" --> M_Drop[Lọc nhiễu / Flickering Cảnh báo giả]
    L -- "Có (Chắc chắn)" --> N[Crop Bounding Box Person]
    
    N --> O[Push Evidence Data lên Central Database]
    O --> P((Kết thúc Frame t))
    
    J --> P
    C_Drop --> P
    M_Drop --> P
```

---

## 7. Lựa chọn Mô hình Học Sâu & Kịch bản Huấn luyện
1. Lựa chọn Mô hình: **YOLOv8 Nano/Small (n/s).** Mô hình nhỏ kết hợp với việc tiền xử lý sạch sẽ (Pre-processed sạch) có thể vượt qua độ chính xác của YOLOv8 Large mà không chịu sức nặng thuật toán dư thừa.
2. Nhãn Huấn Luyện (Classes):
    * `0: helmet` (Chiếc mũ cấu trúc an toàn)
    * `1: person` (Con người đứng làm mốc)
    * `2: pseudo_hat` (Vật thể ngụy trang mũ: Nón cối, áo trùm đầu, xô châu, nón lá - nhằm loại trừ False Positives lách luật công trường).
3. Đánh giá thuật toán: Phân tích dựa trên đường biểu đồ Loss-Function (Box loss, Obj loss, Cls loss) và đánh giá độ chập thông qua Ma trận nhầm lẫn (Confusion Matrix).
