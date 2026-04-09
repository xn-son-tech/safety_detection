# TÀI LIỆU KỸ THUẬT: THIẾT KẾ HỆ THỐNG VÀ PIPELINE XỬ LÝ (Mục 3a)

Tài liệu này cung cấp cấu trúc chi tiết và nền tảng lý luận kỹ thuật (Technical Rationale) để đáp ứng yêu cầu của Mục `3a` trong File Tiêu chí Đánh giá (`criteria.txt`). Sử dụng trực tiếp dữ liệu này làm kịch bản thuyết trình và chèn vào báo cáo Word/Slide.

---

## 1. Xác định các Module xử lý hình ảnh/video

Để đảm bảo hệ thống tiệm cận với chuẩn công nghiệp, luồng dữ liệu không đi thẳng từ Camera vào AI, mà được bảo vệ và tối ưu qua 4 Module độc lập:

*   **Module 1: Pre-processing (Tiền xử lý và làm sạch dữ liệu)**
    *   **Anti-glitch (SSIM):** Trực tiếp đo lường mất mát cấu trúc (Structural Similarity) trên RTSP stream. Loại bỏ các khung hình bị rách (tearing) hoặc mất gói tin mạng.
    *   **Blur Detection:** Dùng toán tử `Variance of Laplacian` theo thời gian thực để nhận diện chóp chuyển động. Tự động drop các khung hình bị thuống (mờ nhòe) do công nhân chạy nhanh.
    *   **Lighting Adjustment:** Ánh xạ biểu đồ tương phản cục bộ `CLAHE`. Tự động cân bằng vùng sáng tối, hóa giải hiện tượng "cháy sáng" hoặc "ngược sáng" do hướng mặt trời mà không gây nhiễu toàn khung ảnh.
*   **Module 2: Feature Extraction & Main Model (Trích xuất & Suy luận)**
    *   Hệ thống sử dụng mạng `YOLOv8` (kiến trúc One-stage CNN) chạy đa nhiệm (multi-task). YOLO sẽ tạo chung các bản đồ đặc trưng (Feature maps) dùng để hồi quy tọa độ (Bounding box regression) cho cả `Người` và `Mũ` đồng thời.
*   **Module 3: Rule Engine & Hậu xử lý (Geometrical Logic)**
    *   `BoT-SORT Tracker`: Cấp phát thẻ định danh (ID) và theo dõi đối tượng trên đa khung hình, bù đắp ảnh hưởng khi Camera hoặc đối tượng chuyển động che lấp nhau.
    *   `Dynamic Aspect Ratio Map`: Không dùng tọa độ cắt cứng. Hệ thống tính tỷ lệ khung hình Người để linh hoạt thiết lập vùng tìm kiếm "Đầu" tương ứng (Chống lỗi phạt nhầm khi công nhân cúi gập gối nhặt đồ vạch ngang màn hình). Đem gộp IoU ghép Mũ vào Đầu.
*   **Module 4: Alert Validation (Bộ lọc Cảnh báo Nhiễu cuối)**
    *   Time-Sliding Window ngăn chặn cảnh báo nhấp nháy do bị chướng ngại vật cản camera trong tích tắc.
    *   Cắt ảnh và đẩy siêu dữ liệu (Metadata: Thời điểm, Tọa độ bounding box, Mức tự tin) vào Database để làm bằng chứng.

---

## 2. Thiết kế Kiến trúc tổng thể & Máy trạng thái hệ thống

Sơ đồ dưới đây (Lưu ý: copy đoạn code này dán vào Notion hoặc bất kỳ công cụ hỗ trợ Mermaid JS để view biểu đồ) minh họa dòng chảy của bất cứ một khung hình nào đi qua hệ thống.

```mermaid
graph TD
    A[Camera RTSP Stream] -->|Raw Frame| B_Pre(Module Tiền xử lý)
    
    subgraph PreProcessing [1. Data Cleaning]
        B_Pre --> B1{Kiểm tra SSIM}
        B1 -- Rách / Packet Loss --> B_Drop[Drop Frame]
        B1 -- Nguyên vẹn --> B2{Lọc Laplacian}
        B2 -- Mờ (Motion Blur) --> B_Drop
        B2 -- Nét --> B3[Cân bằng sáng CLAHE]
    end

    B3 --> C_Model(Module AI Chính)
    
    subgraph MainModel [2. YOLOv8 & Tracking]
        C_Model --> C1[Trích xuất CNN Features]
        C1 --> C2[Phân loại: Person, Helmet, Other_Hat]
        C2 --> C3[Hồi quy Tọa độ Boxes]
        C3 --> C4[BoT-SORT: Cấp Tracking ID]
    end

    C4 --> D_Logic(Module Xử lý Nghiệp vụ & Hậu kỳ)
    
    subgraph PostProcessing [3. Dynamic Rule Engine - Quy tắc Không gian Động]
        D_Logic --> D1[Tính Tỷ lệ Aspect Ratio = Chiều Rộng / Chiều Cao Box Người]
        D1 --> D1_A{Đánh giá Tỷ lệ Góc dáng?}
        D1_A -- W/H > 1.2 (Đang cúi gập ngang) --> D1_B[Tiên đoán Đầu di chuyển: Mở rộng vùng tìm kiếm sang 2 mép sườn]
        D1_A -- W/H <= 1.2 (Đứng / Đi bộ thẳng) --> D1_C[Tiên đoán Đầu ở tĩnh: Giới hạn tìm kiếm ở 25% Top trên cùng dọc]
        
        D1_B --> D2{Khu vực được quy hoạch Đầu có bao lấy Box Mũ không?}
        D1_C --> D2
        
        D2 -- Có (IoU > Threshold) --> D3[Safety: An toàn]
        D2 -- Không / Ở quá xa / Cầm ở tay --> D4[Danger: Thiếu Trang bị]
        
        D3 -. Chuyển biến vào Bộ đệm .-> D5
        D4 -. Chuyển biến vào Bộ đệm .-> D5[Time-Sliding Window buffer = 30 Frames]
        D5 --> D6{Tích lũy đủ tỷ lệ Vi phạm: 25/30 frames liên tiếp?}
    end

    D6 -- Đạt (Xác nhận) --> E_Back(Cập nhật Cơ sở Dữ liệu)
    D6 -- Báo động giả / Cooldown --> E_Drop[Bỏ qua]

    subgraph BackendSystem [4. Backend Storage & Dashboard]
        E_Back --> E1[Đẩy ID vào In-Memory Cooldown_Cache]
        E1 --> E2[Trích xuất Metadata & Crop Bằng chứng]
        E2 --> E3[(Database)]
        E4[Admin Dashboard] <== WebSockets ==> E3
```

### C. Phân tích chi tiết Dòng chảy Dữ liệu (Workflow Analysis)
Sơ đồ trên mô phỏng vòng đời của một khung hình (frame) độc lập kể từ khi được chụp bởi camera. Một khung hình sẽ đi qua 4 giai đoạn nghiêm ngặt:

1.  **Giai đoạn Tiền xử lý (Data Cleaning):**
    *   Hệ thống nhận luồng video thô (**Raw Frame**) từ Camera tới máy chủ dạng luồng mạng. Bước đầu tiên thiết yếu là phòng ngự các lỗi truyền tải mạng. **SSIM** được áp dụng để rà xem gói tin có bị rách, sọc ngang dọc hoặc rơi rụng một nửa (**Packet Loss**) không. Nếu có, frame này bị vứt bỏ để không làm "mù" AI.
    *   Kế đến, toán tử **Laplacian** tính toán mức độ chuyển động. Nếu công nhân chạy vội sinh ra vệt mờ nhòe (**Motion Blur**), frame bị thả trôi. Còn nét, frame vượt qua chốt chặn sẽ được cân chỉnh ánh sáng qua bộ lọc thông minh **CLAHE** để khắc phục nhiễu ngược sáng hoặc dư sáng lóa trắng, tối ưu độ tương phản cho vật thể "Mũ bảo hộ" được rõ nét lên mức tối đa.

2.  **Giai đoạn Suy luận AI (YOLO & Tracking):** 
    *   Bức ảnh "sạch" đi vào AI Chính. Lưới mạng tích chập **CNN** chạy nhiệm vụ trích xuất đặc trưng vật thể. YOLO phân loại các điểm ảnh này rơi vào phân khúc nhóm là `Person`, `Helmet` hay mũ mồi `Other_Hat`.
    *   Đồng thời nó quy hoạch các tọa độ góc để vẽ vòng ôm hình hộp (**Bounding boxes**) xác định vị trí thực thể. Máy lấy được hình ảnh người và mũ, sau đó lập tức đẩy qua **BoT-SORT** để theo dõi và cấp phát mã định danh liên tục (**Tracking ID**) giúp cho dù đối tượng bị che khuất tạm thời, hệ thống vẫn nhớ được họ là ai (chứ không phải đếm lại 1 người thành 2 lần vi phạm).

3.  **Giai đoạn Ràng buộc Kịch bản Logic (Dynamic Rule Engine):**
    *   Hệ thống chạy các thuật toán hình học động. Thay vì chốt cứng vị trí trên cùng hộp người luôn là "Đầu", hệ thống dùng tỷ lệ chiều ngang/chiều dọc của Bounding Box hình người (**Aspect Ratio**) để cảm thấu người đó đang đứng thẳng hay cúi gập cong người (lúc cúi gập thì chiều cao hẹp đi, chiều phình ngang bành ra, đầu sẽ chuồi về vùng cạnh sườn mép ảnh). Ở vùng đỉnh Đầu giả định đó, tính toán tỷ lệ giao thoa **IoU** với hộp Mũ bảo hộ.
    *   Nếu tỷ lệ đè lên nhau đủ lớn theo ngưỡng yêu cầu (**Threshold**), người này an toàn. Ngược lại kết luận tạm thời là vi phạm. Tuy nhiên, nó đưa phán đoán vào Cửa sổ trượt lấy mẫu **Time-Sliding Window**. Phải có đủ 25 trên 30 khung hình gần đây nhất đều có chung kết luận là Vi phạm thì nó mới Xác nhận (ngừa báo lỗi giả chớp cháy khi người đi qua góc khuất tán cây).

4.  **Giai đoạn Lưu trữ & Giao thức Báo động (Storage & Push Notification):**
    *   Thay vì dội bom SQL liên tục hàng nghìn lần làm treo máy, nếu ID vi phạm bị bắt, nó được đẩy vào vùng cách ly tạm trên bộ nhớ tĩnh RAM (**In-Memory Cooldown_Cache**). ID này sẽ bị im lặng thông báo trong tầm 3-5 phút tới nếu tái lặp.
    *   Hệ thống lúc này ra sức cắt ảnh chân dung người vi phạm (Crop) rồi chèn các thông tin chữ đi kèm (**Metadata**), đẩy về CSDL (**Database**). 
    *   Nhờ cổng **WebSockets**, giao diện người trực ở trạm canh (Dashboard) giật báo động đỏ popup Real-time không có độ trễ tải trang.

### D. Giải thích Thuật ngữ Kỹ thuật Viết tắt nằm trong Lưu đồ
*   `RTSP (Real Time Streaming Protocol)`: Giao thức mạng cho phép truyền hình ảnh video theo dòng (stream) từ IP Camera đến máy xử lý với tốc độ trễ siêu thấp (Tốt hơn HTTP).
*   `SSIM (Structural Similarity Index Measure)`: Một chỉ số đo lường nâng cao (khác với đo điểm ảnh thô bằng MSE) dùng để đối chiếu sự nguyên hình cấu trúc gốc trong xử lý ảnh kỹ thuật số. Cốt lõi của việc ngăn cản hình ảnh suy hao vỡ nát do tín hiệu mạng yếu đi sâu vào mạng model.
*   `Packet Loss`: Sự mất mát gói tin. Camera đi bằng cáp LAN hoặc Wifi, khi rớt băng thông, dữ liệu không đến đủ làm khung video rách màn hình xám xịt một phía.
*   `CLAHE (Contrast Limited Adaptive Histogram Equalization)`: Cân bằng Histogram cục bộ giới hạn tương phản. Kỹ thuật chia ảnh làm nhiều ô vuông nhỏ (8x8 tile) và tự tối ưu sáng-tối cho riêng ô vuông đó. Rất hữu hình với hiện tượng ngược sáng công trường.
*   `CNN (Convolutional Neural Network)`: Lớp Nơ-ron tích chập. Nền tảng cốt lõi của Trí tuệ AI Thị giác máy tính nhận diện hình ảnh. Hoạt động trên dạng các hạt nhân trịch xuất ma trận.
*   `BoT-SORT (Bag of Tricks for Simple Online and Realtime Tracking)`: Thuật toán Tracking đối tượng hạng nặng tối ưu tốt nhất hiện giờ, vượt qua DeepSORT do có cơ chế kết hợp với quán tính camera di chuyển và dự phóng bù đắp mất vùng che khuất (Kalman Filter tích hợp Motion bù trừ).
*   `Aspect Ratio`: Tỷ lệ khung (Thường là `Chiều Rộng / Chiều Cao` của bounding box người).
*   `IoU (Intersection over Union)`: Tỷ số diện tích giao thoa tính bằng $\frac{Diện tích phần Giao Cắt}{Diện tích phần Khối Chóp tổng thể}$. Nếu Bbox của cái mũ nằm trọn vớt gọn trên Bbox người ở khu vực đỉnh thì IoU tiến gần 1. 
*   `Threshold`: Giá trị Ngưỡng ranh giới lập trình. Nó giống như bộ lề cài đặt để ra quyết định Logic `IF...ELSE`.
*   `Time-Sliding Window`: Kỹ thuật Cửa sổ trượt qua thời gian mảng phần tử. Nó tạo một dãy Array gồm chiều dài N frame. Khi Frame mới tràn vào, đẩy frame cũ nhất ra khỏi dãy mảng để giữ tính kế thừa thời gian liên tục và bù đắp suy đoán nhiễu gãy (Flickering Filtering).
*   `In-Memory Cooldown_Cache`: Bộ nhớ Cache trên RAM hệ thống (Ví dụ kinh điển là Redis). Dùng RAM để cản dòng rác vì đọc/ghi RAM đạt ngưỡng Mili-giây trong khi chọc SQL ở Ổ đĩa Disk rất tốn IOPS và làm đứng máy.
*   `Metadata`: Siêu dữ liệu mô tả thuộc tính. Ở đây là tổ hợp các Object JSON (Ví dụ: Máy ảnh số 1, Ngày 15/05/2026, Độ tin cậy Model 0.98, Vi phạm...).
*   `WebSockets`: Giao thức TCP hai chiều kết nối duy trì mở. Khác HTTP ở việc client không cần gõ Request liên tục (Pull) mà Server khi có tin mới dội chủ động xịt (Push) về Client. Do đó màn hình quản lý nảy báo động trong 1% Giây.

---

## 3. Lựa chọn Mô hình & Chiến lược Transfer Learning

### A. Lý luận lựa chọn Mô hình
Lựa chọn kiến trúc One-stage (YOLOv8) thay vì Two-stage (như Faster R-CNN) hay Transformer (ViT) dựa trên nguyên tắc trade-off môi trường thực tế:
1.  **Chi phí tính toán môi trường biên (Edge computing):** Đa số camera hoạt động 24/7 cần xử lý local qua máy chủ công trường. YOLO tối ưu cực hạn số lượng phép toán dấu phẩy động (FLOPs), có thể chạy Real-Time (>30FPS) trên GPU tầm trung (như T4 hoặc Jetson). Two-stage bị sụp nghẽn (bottleneck) nếu trong ảnh có mật độ công nhân dày đặc.
2.  **BoT-SORT vượt trội hơn DeepSORT:** Ở môi trường xây dựng, vật cản (cột, máy xúc) xuất hiện liên tục. BoT-SORT sở hữu tính năng theo dõi chuyển động camera và kết hợp góc nhìn không gian, giúp ID công nhân không bị mất hay reset khi họ lùi ra sau tường rồi đi ra lại.

### B. Chiến lược Huấn luyện Model (Training Strategy)
Hệ thống sử dụng kỹ thuật Huấn luyện tiếp chuyển (Transfer Learning) từ bộ tạ có sẵn (Pretrained Weights trên tập COCO) để tăng tốc độ hội tụ và độ linh hoạt cho các biên khối hình.

**1. Kỹ thuật "Hard-Negative Mining" thông qua phân loại 3 Nhãn (3 Classes):**
Thay vì mô hình Nhị phân kinh điển (`Có đội mũ` / `Không đội mũ`), ta đưa hệ thống vào trạng thái Cố tình đặt bẫy:
*   Mô hình được Train với 3 Lớp: `Helmet` (Mũ bảo hộ cứng theo chuẩn), `Other_Hat` (Nhãn mồi: Nón lá, mũ xe máy, mũ len, nón vải...), và `No_Helmet`. 
*   Việc ép mạng Model tự học khác biệt giữa Mũ chuẩn và Mũ vải triệt tiêu hoàn toàn tỷ lệ Dương tính giả (False Positives) dành cho những trường hợp cố tình dùng nón lá để lách luật tại công trường.

**2. Chiến lược Tăng cường Dữ liệu Đặc thù (Data Augmentation):**
*   **Hệ màu HSV thay vi Hệ màu RGB truyền thống:** Không dùng thao tác nhiễu RGB thông thường. Hệ màu HSV (Hue - Saturation - Value) được sử dụng để tách bạch ánh sáng (V) ra khởi phổ màu của Mũ (H). Nhờ augment trên Value, lưới Model trở nên "miễn nhiễm" với các hiện tượng Mũ bảo hộ bằng nhựa bóng bị chói/lóa sáng dưới góc nắng gắt.
*   Kết hợp thuật mã hóa cắt xén hình ảnh (`Mosaic augmentation`) để mô phỏng sự hỗn loạn khi có cụm đám đông công nhân che lấp nhau.
