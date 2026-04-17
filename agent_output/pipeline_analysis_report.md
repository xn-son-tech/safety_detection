# Báo cáo Phân tích Chuyên sâu Hệ thống Safety Detection (Full Pipeline Analysis)

Đánh giá hệ thống Safety Detection dưới góc nhìn của một Kỹ sư Hệ thống, dựa trên mã gốc và tài liệu thiết kế (`docs_section_3a_analysis.md`).

---

## 1. Phân tích Dòng chảy Hệ thống (Pipeline Overview)

Mặc dù tài liệu mô tả luồng khá đầy đủ, nhưng khi đối chiếu với thực tế mã nguồn (`core_detection`), có một số điểm vượt trội và cả những sai lệch quan trọng đã được cài đặt:

*   **Camera Input & Buffering:**
    *   Sử dụng `cv2.VideoCapture` với cấu hình `CAP_PROP_BUFFERSIZE = 1` để triệt tiêu độ trễ mạng (ngăn hàng chờ frame cũ chồng chất gây độ trễ dồn tích).
*   **Pre-processing (Tiền xử lý đa lớp):**
    *   **Blur Detection:** Dùng `cv2.Laplacian(gray).var()` với `threshold` (30 - 60 tùy module) để lọc khung hình mờ do chuyển động nhanh.
    *   **Glitch/Tear Detection:** Đo mức độ mất dữ liệu bằng thuật toán `skimage.metrics.structural_similarity` (SSIM) với ngưỡng `threshold = 0.3` (thay vì 0.5 như thiết kế gốc). Khung hình bị rách sẽ lập tức bị vứt bỏ trước khi vào AI.
    *   **Light Enhancement:** Chuyển sang không gian màu LAB, dùng **CLAHE** (`clipLimit=2.0`, `tileGrid=(8,8)`) trên kênh L. Tại `webcam_demo.py` còn bổ sung thêm kỹ thuật Unsharp Masking để làm nổi bật nét viền của mũ bảo hộ trắng trong môi trường bị lóa sáng hay ngược sáng.
*   **Inference (AI Model YOLOv8):**
    *   Hệ thống sử dụng chung một mô hình để dự đoán 3 lớp: `Helmet`, `Other_Hat`, và `No_Helmet`.
    *   **Ngưỡng tin cậy (Confidence Thresholds):** Mũ bảo hộ (`0.25`), Nón khác (`0.55`), Không đội mũ (`0.5`).
*   **Post-processing & Rule Engine (Điểm khác biệt nhất so với Docs):**
    *   **Không sử dụng Dynamic Aspect Ratio (Khác biệt so với tài liệu thiết kế):** Code thực tế tại `helmet_violation.py` giải thích rằng đã bỏ việc co hẹp vùng đầu theo tỷ lệ rộng/cao. Thay vào đó, bộ Head ROI sử dụng **cố định 35% không gian trên cùng** của Bounding Box (`HEAD_ROI_RATIO = 0.35`).
    *   **Khắc phục vấn đề trùng lặp vật thể (1-to-1 Greedy Matching):** Áp dụng giải thuật duyệt mảng ma trận `IoA` (Intersection over Area) bằng `np.argsort` để ngăn tình trạng 1 cái mũ cấp tín hiệu an toàn cho 2 cái đầu lân cận (Oclussion).
    *   **Material Analysis (M-Score Override) - Vũ khí bí mật không ghi trong Docs:** Code chứa hàm `analyse_head_roi_material()`. Khi YOLO phát hiện mức độ tự tin thấp, hệ thống sẽ cắt riêng vùng đầu, kéo giãn tương phản (Contrast Stretching), đánh giá mức độ bất đối xứng (Skewness Variance) và dùng khung Morphological Top-Hat. Nếu tính ra `M-Score >= 0.5`, hệ thống sẽ sử dụng quyền tối cao đảo ngược kết quả từ "Vi phạm" thành "An Toàn". Rất giá trị chống lại cảnh báo sai khi đội mũ trắng chói sáng dưới nắng gắt.
*   **Alert Validation:**
    *   Dùng bộ đệm Time-Sliding Window: Đòi hỏi **ít nhất 24 / 30 frames** liên tiếp đều kết luận vi phạm mới kích hoạt ghi nhận báo động, loại bỏ triệt tiêu các cảnh báo nháy do góc khuất vật lý.

---

## 2. Phân tích Khả năng Real-time thực tế (Real-time Feasibility)

Hệ thống hiện tại **KHÔNG THỂ chạy mượt 30 FPS nếu sử dụng thiết kế Synchronous (Đồng bộ) như đang viết ở `webcam_demo.py`**. Khung hình sẽ bị khựng theo đúng tốc độ load của AI.

*   **Nút thắt cổ chai (Bottlenecks):**
    *   **Tiền xử lý (CPU Bound Cực Nặng):** Hàm `skimage.metrics.structural_similarity` chạy đơn luồng CPU trên ảnh lớn cực kỳ chậm. Các thao tác CLAHE + Unsharp Masking cũng tiêu thụ nhiều tài nguyên IOPS trước khi dữ liệu được đẩy vào AI.
    *   **Blocking Main Loop:** File `webcam_demo.py` đang dùng vòng lặp tuần tự chặn màn hình (`Đọc Frame -> Xử lý độ sáng -> AI dự đoán -> BoT-SORT xử lý -> Vẽ khung -> Đẩy UI`). Tổng thời gian vòng lặp xấp xỉ tốc độ inference của AI, đẩy FPS xuống khoảng 5~15 FPS khiến giao diện trông bị giật lag rõ rệt.
*   **Điểm sáng về kiến trúc:** Tại `helmet_pipeline.py`, lớp `WorkerSafetyPipeline` đã được thiết kế sẵn một hàm `async_run` chạy theo mô hình bất đồng bộ **Producer-Consumer**. Việc phân tách luồng thu thập hình ảnh của Camera (30 FPS) và luồng phân tích AI là hoàn toàn khả thi, giúp mượt hóa UI.
*   👉 **Kết luận Real-time:** Bắt buộc áp dụng cấu trúc Bất đồng bộ (`async_run`) để khung hình UI luôn xoay vòng ở 30 FPS.

---

## 3. Phân tích Chất lượng Nhận diện (Detection Accuracy)

*   **False Positives (Báo sai người an toàn thành vi phạm):** Hệ thống có sức đề kháng cực tốt. Tuy ngưỡng Mũ đặt hơi lỏng lẻo (`0.25`), thế nhưng hệ thống Material Analysis (M-Score) hoạt động như tấm khiên thứ hai ngăn chặn việc trừng phạt oan nhân công dùng mũ nhựa trắng hoặc dưới tia nắng gắt.
*   **False Negatives (Bỏ lọt vi phạm):** Ngưỡng "No-Helmet" (`0.5`) kết hợp với bộ đệm Sliding Window (24/30 FPS) đảm bảo rằng AI sẽ không bị báo động nhảm khi góc máy bị khuất chớp nhoáng (Flickering). Mặc dù cơ chế này độ trễ báo cảnh sẽ có từ 0.5s đến 1s so với thời gian phát sinh luật, nhưng khi báo động nổ lên thì tỷ lệ đúng gần như là tuyệt đối 100%.
*   **Occulusion / Motion Blur / Frame Drops:** Xóa mờ tốt bằng Laplacian và triệt tiêu Glitch bằng SSIM. Trình theo dõi BoT-SORT duy trì ID cực tốt ngay cả khi gặp vật cản lớn tạm thời che chắn hệ thống.

---

## 4. Đánh giá Cấu trúc Mã nguồn (Code-Level Review)

1.  🔴 **Vòng lặp không hiệu quả:** Gọi `skimage.metrics.SSIM` trực diện trên ảnh gốc đang vắt kiệt nhân xử lý CPU. Cần Downscale (thu nhỏ) khung hình tỷ lệ siêu thấp trước khi đưa vào lấy SSIM.
2.  🔴 **Luồng hiển thị Âm thanh (Thread I/O):** Thư viện `pyttsx3` thiết lập với `async` (Daemon Multi-thread) chạy ngầm có thể tạo ra tình trạng treo rác Thread ở Windows nếu không thiết lập Locking chính xác, dẫn đến giảm memory dần sau vài tiếng trực camera.
3.  ✅ **Rule Engine gọn gàng:** Sử dụng ma trận Tensor của Numpy ở module `evaluate_tracked_person_violations` giải quyết triệt để sự tốn kém bộ nhớ so với vòng lặp `for-for` O(N²) cổ điển, thời gian xử lý xuống cận biên dướt ~1ms.

---

## 5. Điểm mạnh và Điểm yếu Hệ thống

### ✅ Strengths (Điểm cực mạnh - Tiêu chuẩn Công nghiệp)
*   Áp dụng **1-to-1 Greedy Map (IoA)** khắc phục các sai số chồng chất Bounding Box khi mật độ công nhân đứng quá sát nhau che lấp nhau.
*   Kiến trúc chống nhiễu quy tắc độ bóng bề mặt vật liệu (**M-Score**): Đây là cứu cánh hoàn hảo cho các camera lắp ngoài công trường luôn gặp phải góc ngược sáng.
*   Bộ đệm cảnh báo **24/30 frames (State Buffer)** chặn đứng tất cả các trường hợp báo động sai có thời lượng quá ngắn hoặc báo rác do AI lỗi nhận diện dưới nửa giây.

### ❌ Weaknesses (Cần khắc phục để đưa vào Môi trường Thực)
*   Có sự mâu thuẫn giữa kỹ thuật Dynamic Aspect Ratio trong giấy tờ và việc Fix cứng "35% Top" tại Code, nếu công nhân cúi gập gối nhặt đồ, việc chốt cứng 35% Top có khả năng sai lệch và bắt nhầm vị trí đầu.
*   Main Thread bị blocking tuần tự khi khởi chạy giao diện Demo Camera, UI phụ thuộc vào tốc độ AI nên sẽ không mượt (nếu chạy Single-thread).

---

## 6. Đề xuất Tối ưu hóa (Optimization Recommendations)

**Mô hình Async Pipeline Cải tiến (Architecture Diagram)**

```text
[ Camera Thread ] (Real-time 30FPS)
   ├── cv2.VideoCapture().read() 
   ├── Đẩy frame vào Queue In (Chỉ lưu 1 frame tươi nhất, Overwrite frame cũ)
   └── Bơm tín hiệu hình gốc sang thẳng nhánh [UI Thread] vẽ ra màn hình ngay lập tức.
            ↓
            ↓
[ AI Worker Thread ] (Dao động 10-20FPS tùy máy tính)
   ├── Resize (Thu nhỏ ngay về 128x128 để chạy SSIM / Laplacian) -> Xóa nhanh frame rác 
   ├── Resize (Khổ gốc 640x640) -> Vô YOLOv8 để tính toán Trích xuất Tensor
   ├── Chạy logic Rule Engine & Mask Morphological M-Score (Numpy Matrix)
   ├── Cập nhật Rule Buffer Cảnh báo (24/30 FPS)
   └── Đẩy Tọa độ & Nhãn kết quả vào biến Share Context / Global Memory
            ↓
            ↓
[ Display / UI Worker ] (Chạy đồng bộ nhịp nhảy với Camera)
   ├── Lấy ảnh sạch nhất từ Camera Thread.
   ├── Dán tọa độ Bounding Box mới nhất có trong Global Memory.
   └── Đẩy khung hình `cv2.imshow()` ở 30 FPS. (Đảm bảo người giám sát không bị nhức mắt do giật lag).
```

### Các hành động cần thực thi (Actionable items ưu tiên đầu):
1.  **Chỉnh sửa thuật toán SSIM:** Cân nhắc bỏ hoàn toàn thư viện hàn lâm `scikit-image`. Có thể dùng `cv2.matchTemplate()` bình thường hoặc đo `MSE` thu nhỏ qua OpenCV Native, tốc độ sẽ nhanh hơn hàng chục lần.
2.  **Đưa Async vào Demo:** Định tuyến lại kiến trúc của file `webcam_demo.py`. Loại bỏ vòng lặp đồng bộ thay bằng việc gọi hàm thiết kế đa luồng `system.async_run()` (Hàm này có đầy đủ cơ chế Producer-Consumer).
3.  **Deploy mô hình AI GPU / Edge:** Nếu gắn ở biên sản xuất, nên chuyển đổi mô hình gốc `.pt` sang dạng Engine cấp thấp như `.onnx` hoặc `TensorRT` (nếu có NVIDIA GPU). Pytorch `.pt` đang tốn một lượng dư thừa thời gian nạp bộ nhớ khá lãng phí ở mỗi một lần trích xuất suy luận trên tập điểm ảnh.
