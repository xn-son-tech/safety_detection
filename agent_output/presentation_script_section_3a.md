# Kịch bản Thuyết trình: Quá trình Xử lý Nhận diện Mũ Bảo hộ (Mục 3a)

**[Mở đầu]**
"Xin chào mọi người. Hôm nay, tôi xin phép trình bày chi tiết về kiến trúc tổng thể và vòng đời của một khung hình khi đi qua hệ thống nhận diện vi phạm an toàn của chúng ta. Thay vì đưa thẳng video vào trí tuệ nhân tạo (AI), hệ thống được thiết kế thành 4 module độc lập như những trạm kiểm duyệt, đảm bảo tính chính xác và chống nhiễu tuyệt đối. Mời mọi người nhìn vào lưu đồ trên màn hình.

---

### [Trạm 1: Tiền xử lý & Làm sạch Dữ liệu - Data Cleaning]
Đầu tiên, hệ thống sẽ nhận dữ liệu trực tiếp từ các camera ngoài công trường dưới dạng luồng **RTSP** *(Real Time Streaming Protocol - Giao thức truyền phát thời gian thực, giúp truyền video siêu tốc độ qua mạng)*. Một khung hình thô vừa tới sẽ gặp ngay trạm gác đầu tiên:

1. **Bước kiểm tra độ nguyên vẹn:** Ở đây, hệ thống tính toán chỉ số **SSIM** *(Structural Similarity Index Measure - Chỉ số đo lường sự tương đồng cấu trúc ảnh)* để phát hiện xem đường truyền mạng có ổn định không. Nếu mạng lag gây ra **Packet Loss** *(Mất gói tin, làm ảnh bị rách hoặc xám đi mảng lớn)*, khung hình này sẽ bị loại bỏ ngay lập tức (Drop) để không làm "mù" mạng AI.
2. **Bước kiểm tra độ nét:** Nếu ảnh nguyên vẹn, nó đi tiếp qua bộ lọc Laplacian để bắt các vệt mờ. Đôi khi công nhân chạy vội sinh ra hiệu ứng **Motion Blur** *(Mờ nhòe do chuyển động nhanh)*, bức ảnh mờ đó cũng sẽ bị loại bỏ.
3. **Bước cân bằng ánh sáng:** Khi một khung hình đã "Sạch" và "Nét", hệ thống chạy nó qua bộ lọc **CLAHE** *(Contrast Limited Adaptive Histogram Equalization - Thuật toán cân bằng tương phản cục bộ)*. Chức năng này đặc trị hiện tượng công trường bị ngược sáng nổ trắng hoặc quá tối, giúp "cái mũ" hay "con người" vùng đó hiện ra sắc nét đến mức tối đa.

---

### [Trạm 2: Trí tuệ Nhân tạo & Nhận diện - YOLOv8 & Tracking]
Sau khi có bức ảnh hoàn hảo nhất, nó mới được bơm vào "bộ não" của hệ thống - Module AI Chính:

1. AI sẽ trích xuất ngay các điểm ảnh thông qua mạng **CNN** *(Convolutional Neural Network - Mạng nơ-ron tích chập, chuyên gia số 1 trong thị giác máy tính hiện nay)*.
2. Mô hình AI đa nhiệm (YOLOv8) sẽ thực hiện hai việc cùng lúc: Phân loại đó là Người, Mũ bảo hộ hay Mũ mồi (Ví dụ: nón lá, mũ xe máy) và vẽ tọa độ vùng bao quanh vật thể dạng hình hộp chữ nhật (**Bounding Boxes**).
3. Ngay khi bắt được tọa độ, dữ liệu được móc nối vào ngay hệ thống **BoT-SORT** *(Bag of Tricks for Simple Online and Realtime Tracking - Thuật toán gán và bám sát mục tiêu cao cấp nhất)*. BoT-SORT sẽ phát cho người đó 1 mã định danh (**Tracking ID**). Nhờ đó, nếu chú công nhân bị cột sắt che khuất 2 giây rồi đi ra, hệ thống vẫn "nhớ mặt" và biết đó là ID cũ, không tính nhầm thành 2 người vi phạm khác nhau.

---

### [Trạm 3: Quy tắc Không gian Động - Dynamic Rule Engine]
Có ID người và mũ rồi, làm sao để AI biết chú công nhân CÓ ĐANG ĐỘI mũ hay không (chứ không phải đang vứt ở dưới đất)? Đây là lúc thuật toán hình học động lên tiếng:

1. Đầu tiên, hệ thống đo tỷ lệ **Aspect Ratio** *(Tỉ lệ giữa Chiều Rộng và Chiều Cao - **W/H** của khung hộp quanh người)*. 
2. **Tại sao lại phải đo?** Vì nếu công nhân đang đứng thẳng, hệ thống sẽ hiểu vùng cần tìm kiếm "cái mũ" nằm ở đỉnh 25% phía trên cùng. Nhưng nếu công nhân **đang cúi gập gối để nhặt xẻng** (tỉ lệ W/H > 1.2), đỉnh đầu sẽ chĩa ra hai bên sườn màn hình, hệ thống sẽ "động não" tự mở rộng phạm vi tìm đỉnh đầu sang hai mép. Thiết kế thông minh này cứu hệ thống khỏi bệnh "Báo động giả khi công nhân cúi người" - nỗi đau của rất nhiều dự án AI khác.
3. Khi quy hoạch đúng vị trí đỉnh đầu tiềm năng, nó chồng hộp Mũ lên hộp Đầu, đối chiếu qua tỷ lệ **IoU** *(Intersection over Union - Tỉ số tính % diện tích phần đè lên nhau giữa hai hình hộp)*. Nếu tỉ lệ đè lên nhau cao (đạt **Threshold** - *Ngưỡng cho phép*), người này an toàn. Ngược lại, tính là Vi phạm.
4. **Tuy nhiên, chưa báo động vội!** Kết quả bị vi phạm sẽ đi vào bộ đệm lấy mẫu **Time-Sliding Window** *(Cửa sổ thời gian trượt xoay vòng liên tục)* chứa 30 khung hình gần đây nhất. Mọi chuyện chỉ được xác nhận chắc chắn là vi phạm NẾU có đến 25/30 khung hình gần nhất (tương đương gần 1 giây thực tế) đều báo vắng bóng chiếc mũ. Điều này làm triệt tiêu lỗi chớp nháy vô tình khi công nhân lướt qua tán cây.

---

### [Trạm 4: Lưu trữ & Báo động sấm sét - Backend Storage & Dashboard]
Khi Vi phạm được xác nhận ở Trạm 3, nó sẽ bóp còi báo động qua Trạm 4:

1. Hệ thống lập tức cắt 1 bức ảnh chân dung vi phạm (**Crop Image**), đóng gói cùng **Metadata** *(Siêu dữ liệu dạng chữ, ví dụ: Camera số 1, Ngày 15/05, Tọa độ X-Y, Tỉ lệ chắc chắn 98%...)* và lưu bằng chứng vào Cơ sở dữ liệu (**Database**).
2. Để tránh việc dội bom báo động làm đơ máy chủ hay ngập lụt màn hình của bác bảo vệ, ID của công nhân vừa bị chộp sẽ ngay lập tức bị ném vào vùng tàng hình **In-Memory Cooldown_Cache** *(Bộ nhớ đệm trên RAM máy chủ xử lý cực nhanh)*. Anh này mà có lượn qua lượn lại thêm 2-3 phút nữa thì cũng không bị reo kèn spam thứ 2.
3. Và cuối cùng, ngay ở khoảnh khắc bức ảnh bằng chứng ra đời, thông qua đường hầm **WebSockets** *(Giao thức kết nối mở liên tục hai chiều, tốc độ giật hiển thị nhanh hơn HTTP)*, một lá cờ đỏ sẽ nảy Pop-up theo thời gian thực (Real-time) trên màn hình Admin, không có độ trễ tải trang.

---

**[Kết thúc]**
Đó là toàn bộ vòng đời khép kín cực kỳ chặt chẽ và thông minh của hệ thống. Xin cảm ơn sự cố gắng lắng nghe của mọi người!
