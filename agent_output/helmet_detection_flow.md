# Tài liệu Thiết kế chuyên sâu: Luồng xử lý Nhận diện Mũ bảo hộ (Deep Dive Helmet Detection Flow)

Tài liệu này cung cấp thiết kế toàn diện cho phân hệ **Nhận diện Mũ bảo hộ (Helmet Detection)**, phân tích chi tiết mọi ngoại lệ (exceptions) có thể phát sinh trong môi trường công trường thực tế và đưa ra các quyết định kỹ thuật kèm theo dẫn chứng cụ thể (Trade-off & Rationale).

---

## Bước 1: Thu nhận và Tiền xử lý dữ liệu (Frame Capture & Pre-processing)
*Quy trình bắt hình ảnh từ stream Camera (RTSP) và tối ưu hóa chất lượng hình ảnh.*

### 🛠️ Các ngoại lệ (Exceptions):
1. **Khuyết tật luồng Stream (RTSP Glitch / Artifacts / Packet Loss):** Hình ảnh bị nhiễu sọc màu, rách hình (tearing) hoặc xám một nửa do mạng yếu.
2. **Khung hình mờ do chuyển động (Motion Blur):** Công nhân chạy nhanh hoặc camera bị gió thổi rung lắc, gây mất nét.
3. **Môi trường chói sáng / Phản quang mạnh / Ngược sáng (Backlight / Halation):** Bị mặt trời chiếu trực tiếp vào ống kính dẫn tới người biến thành bóng đen (silhouette).
4. **Mật độ sáng yếu ban đêm hoặc do thời tiết xấu (Low-light).**
5. **Vật cản dính vào mặt kính Camera:** Hạt mưa, mạng nhện, bụi bám.

### 💡 Hướng giải quyết & Dẫn chứng kỹ thuật (Rationale):
* **Giải pháp 1: Áp dụng Structural Similarity Index (SSIM) hoặc kiểm tra File Header thay vì Mean Squared Error (MSE) cho lỗi RTSP.**
  * *Tại sao:* MSE chỉ đo trung bình điểm ảnh, không hiểu được cấu trúc. Khung hình xám một nửa vẫn có thể qua mặt. SSIM đo lường mức độ phá hủy cấu trúc hình ảnh, loại bỏ dứt điểm các frame bị rách do packet loss. Bỏ qua frame lỗi giúp AI không suy luận kết quả rác.
* **Giải pháp 2: Bộ lọc Variance of Laplacian để phát hiện mờ (Blurry Detection).**
  * *Tại sao dùng Laplacian thay vì Fast Fourier Transform (FFT):* Tính toán biến thiên của thuật toán Laplacian cực kỳ nhẹ và nhanh (Real-time). FFT cũng phân tích tầng số không gian nhưng chi phí toán học quá tốn kém để chạy trên từng frame camera. Threshold của Laplacian nhỏ hơn mức quy định -> drop frame.
* **Giải pháp 3: Xử lý ánh sáng bằng thuật toán CLAHE (Contrast Limited Adaptive Histogram Equalization).**
  * *Tại sao CLAHE khác biệt với Histogram Equalization (HE) thông thường:* HE phân phối lại độ sáng cho toàn bộ khu vực, nên ở những vùng có nhiễu (noise) thì sẽ bị khuếch đại nhiễu lên mất kiểm soát. CLAHE chia hình ảnh thành các block nhỏ và giới hạn mức độ khuếch đại độ tương phản. Giải quyết triệt để ngược sáng mà không làm suy giảm chất lượng chung.

---

## Bước 2: Nhận diện thực thể "Người" (Person Detection)
*Sử dụng YOLOv8 để trích xuất hộp bao (Bounding Box) của Công nhân.*

### 🛠️ Các ngoại lệ (Exceptions):
1. **Bị che khuất một nửa (Partial Occlusion):** Công nhân đứng sau ụ bê tông, máy xúc (chỉ thấy phần thân trên hoặc bị lấp thân trên chỉ thấy chân).
2. **Đám đông quá đứng sát nhau (Dense Crowd Overlap):** 5-10 công nhân quây quần, Bounding box chồng chéo cục diện lên nhau.
3. **Tư thế bất thường (Atypical Postures):** Công nhân bò, quỳ, khom lưng hoặc cúi rạp người.
4. **Cạnh viền khung hình (Truncated boxes):** Nửa người lọt vào camera, nửa người đi ra ngoài.
5. **Báo động giả (False Positives):** Máy móc hình trụ, cột đèn, hoặc bù nhìn được nhận diện thành người.

### 💡 Hướng giải quyết & Dẫn chứng kỹ thuật (Rationale):
* **Giải pháp 1: Dùng Tracking Model (BoT-SORT / DeepSORT) gán ID cố định.**
  * *Tại sao BoT-SORT thay vì DeepSORT thuần:* Khi đám đông che khuất nhau 1-2 giây rồi tách ra, DeepSORT hay bị hiện tượng gán ID mới, làm đứt gãy luồng theo dõi. BoT-SORT kết hợp cân bằng ảnh di chuyển (Camera Motion Compensation) nên nhớ ID cực tốt kể cả có bị che khuất tạm thời.
* **Giải pháp 2: Xử lý Crowds bằng Soft-NMS (Soft Non-Maximum Suppression) trong quá trình hậu kỳ YOLO.**
  * *Tại sao Soft-NMS thay vì Greedy NMS:* NMS truyền thống sẽ xóa bỏ mọi Bbox lân cận nều chỉ số giao thoa (IoU) cao. Nếu hai người đứng quá sát, NMS truyền thống sẽ chỉ hiển thị 1 người (người kia bị xóa). Soft-NMS không xóa mà chỉ giảm điểm tự tin của người thứ 2, giúp giữ lại đầy đủ người trong đám đông.
* **Giải pháp 3: Kĩ thuật Edge-exclusion (Loại bỏ viền ngoài roi).**
  * *Tại sao:* Mặc dù người ở rìa ảnh được detect, nhưng phần Đầu có thể nằm ngoài camera. Nếu cố phát hiện mũ sẽ ra lỗi "Không có mũ". Việc loại bỏ các `person` bbox chạm vào mép biên sẽ giữ sạch luồng dữ liệu.

---

## Bước 3: Phát hiện Đầu & Mũ (Head/Helmet Detection)
*Xác định công nhân đang đội vật thể gì trên đầu.*

### 🛠️ Các ngoại lệ (Exceptions):
1. **Sự tương đồng về hình dáng & Nhầm lẫn mũ thường:** Đội nón lá, mũ hoddie, mũ len, mũ lưỡi trai, quấn khăn thay vì mũ bảo hộ đúng quy chuẩn.
2. **Sự tương đồng màu sắc với nền (Clutter Background):** Mũ màu vàng đứng trước chiếc máy xúc màu vàng; Mũ màu trắng phản chiếu lên kính công trình.
3. **Hiện tượng lóa chói (Specular Reflection):** Nắng gắt chiếu vào mũ nhựa bóng biến điểm ảnh thành màu trắng (điểm cháy sáng).
4. **Góc quan sát khó:** Camera hướng thẳng từ đỉnh đầu xuống (Bird-eye view) hoặc quan sát từ đuôi gáy lên (chỉ thấy phần quai/gáy, không dạng mũ vòm).

### 💡 Hướng giải quyết & Dẫn chứng kỹ thuật (Rationale):
* **Giải pháp 1: Chiến lược Data Hard-Negative Mining với 3 Classes (Helmet, Other_Hat, No_Helmet).**
  * *Tại sao mở rộng 3 Label thay vì 2 (Đội mũ/Không đội mũ):* Nếu chỉ 2 label, AI sẽ có khuynh hướng ép mũ len, nón lá vào một trong 2 lớp đó. Chèn thêm class `Other_Hat` giúp model phân định rõ ranh giới hình học. Đây là kĩ thuật tạo "Mồi" (Negative samples) tốt nhất để triệt tiêu False Positive của công nhân 'lách luật' bằng mũ thời trang.
* **Giải pháp 2: Sử dụng Không gian màu HSV trong Data Augmentation thay vì RGB.**
  * *Tại sao:* Không gian RGB trộn lẫn độ chói (lóa) và màu. Nếu lóa, RGB hỏng hết giá trị r,g,b. HSV tách riêng độ sáng (Value) và màu sắc (Hue). Train model bằng ảnh tăng cường qua hệ hệ màu HSV giúp model chịu đựng được độ lóa sáng (Specular Reflection) mà không mất định dạng mũ vàng/trắng.
* **Giải pháp 3: Kiến trúc One-stage (YOLO multi-class) thay vì Two-stage (Cắt hình Người -> Đưa vào ResNet phát hiện Mũ).**
  * *Tại sao:* Xử lý real-time. Two-stage sẽ cực kì nặng nếu trong ảnh có 30 người (mất 30 lần forward pass lớp ResNet). YOLO có thể giải quyết bài toán phát hiện Mũ đồng thời khi phát hiện Người trên cùng 1 feature map, tiết kiệm tài nguyên GPU.

---

## Bước 4: Ánh xạ Hình học (Geometrical Association - Rule Engine)
*Xác định: Cái mũ A có đúng là được đội trên đầu của Người B không?*

### 🛠️ Các ngoại lệ (Exceptions):
1. **Cầm tay hoặc kẹp nách:** Mũ ở trong diện tích của `Person` nhưng đang bị cầm lủng lẳng dưới hông.
2. **Ảo ảnh không gian 2D (Perspective Illusion):** Mũ của ông A đứng đằng sau cách 5 mét, vô tình nằm trúng vị trí gáy / đầu của ông B (người Không Đội Mũ) đang đứng ngay sát camera rát màn hình.
3. **Mũ rơi vãi dưới đất, ngay chân công nhân.**

### 💡 Hướng giải quyết & Dẫn chứng kỹ thuật (Rationale):
* **Giải pháp 1: Heuristic khu vực giải phẫu đầu (Top 1/4 Body Region).**
  * *Tại sao gọi đây là thuật giải logic mạnh mẽ:* Không cần dùng mạng Pose Estimation phân tích các khớp xương (cực tốn phần cứng GPU). Bằng phép toán xác định Top 1/4 của Bbox `Person`, ta có Vùng Khả Dĩ chứa đầu. Nếu `Helmet` Bbox không rơi vào vùng này đoạn giao diện (Intersection) == 0 -> Chắc chắn mũ không ở trên đầu (rơi dưới chân, hoặc cầm tay).
* **Giải pháp 2: Giải thuật Hungarian (Hungarian Algorithm) cho bài toán ghép đôi qua IoU/Kích thước.**
  * *Tại sao không dùng thuật toán Láng giềng gần nhất (Nearest Neighbor):* Nếu dùng khoảng cách để nối Mũ với Người, cái mũ ở phía sau có chiều cao tọa độ 2D có thể nằm gần hộp trung tâm (centroid) người B hơn cả người A (người chịu trách nhiệm mũ). Hungarian xây dựng ma trận Chi phí (Cost Matrix) dựa trên tọa độ, diện tích và giải quyết bài toán phân bố tối ưu toàn cục (Global Optimization), bẻ gẫy hiệu ứng ảo ảnh 2D góc máy.

---

## Bước 5: Hậu xử lý & Quyết định (Post-Processing & Decision Making)
*Quyết định lúc nào sẽ báo động và ghi vào Database.*

### 🛠️ Các ngoại lệ (Exceptions):
1. **Nhấp nháy phát hiện (Flickering/Glitch):** Công nhân 100% đang đội mũ, bước qua vũng nước loá phản quang, AI mất dấu mũ 1 frame (0.03 giây). Phạt sai oan uổng.
2. **Spam cảnh báo & ngập DB:** Người vi phạm cố tình đứng lì trước ống kính 1 tiếng, hệ thống ở backend có thể bị oanh tạc bởi 108.000 frame gửi API lên -> Sập DB hoặc kẹt băng thông.
3. **Người đi khuất tường rồi mới xử lý xong:** Độ trễ (Latency).

### 💡 Hướng giải quyết & Dẫn chứng kỹ thuật (Rationale):
* **Giải pháp 1: Hysteresis Buffer / Cửa sổ trượt thời gian (Time-Sliding Window Voting).**
  * *Tại sao:* Không ai lưu vi phạm dựa trên 1 tấm ảnh duy nhất vì rủi ro nhiễu nhiễu hạt quá lớn. Hệ thống vận hành theo Rule: Theo dõi theo ID công nhân. Dùng window size N=30 frame. NẾU trong 30 frame gần nhất có > 25 frame là Không đội mũ THÌ mới kết luận vi phạm. Giúp tỷ lệ chuẩn xác xấp xỉ tuyệt đối tại môi trường ổn định.
* **Giải pháp 2: Cơ chế Timeout Cooldown (Dập tắt Spam) qua In-memory Buffer.**
  * *Tại sao không lưu thằng vào Database để check Cooldown:* Nếu mỗi frame đều chọc vào DB để hỏi "Thằng ID#12 này bị phạt trong 5 phút qua chưa?" thì DB sẽ chết vì quá tải truy xuất. Phải tạo Cooldown List trên RAM (Python Dictionary hoặc Redis Cache). Khi báo vi phạm, ghi nhớ Timestamp vào RAM. Mặc định chặn tất cảnh báo tiếp theo của ID#12 trong 5 phút. Vừa nhẹ Backend API mượt mà, vừa có đủ bằng chứng tĩnh đưa lên Dashboard.
