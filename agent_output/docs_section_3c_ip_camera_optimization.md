# Tối Ưu Hóa & Mở Rộng Hệ Thống Cho Camera Nhúng Mạng (IP Camera / RTSP / Mobile App)

Tài liệu thiết kế kiến trúc xử lý độ trễ mạng (Network Latency & Buffering) cho hệ thống Computer Vision chuẩn công nghiệp.

---

## 1. Điểm Khác Biệt Giữa Webcam Cục Bộ vs IP Camera Stream

Việc chuyển mã nguồn từ Webcam (USB/Cáp) sang Camera Điện thoại qua mạng wifi (DroidCam, RTSP, HTTP MJPEG) kéo theo 3 vấn đề chí mạng ảnh hưởng tới Real-time AI:

*   **Độ Trễ Tích Lũy (Buffering Delay - Rất Nguy Hiểm):** Webcam đẩy frame trực tiếp vào RAM. Trong khi đó, IP Camera truyền qua giao thức mạng (TCP/UDP, H264). Thư viện giải mã mặc định của OpenCV (thường là FFmpeg) có thói quen **tự động lưu trữ (buffer) một lượng lớn frames** (có thể lưu sẵn 5 - 10 giây). Việc đọc tuần tự `cap.read()` sẽ lấy những frame từ... 5 giây trước, khiến hệ thống báo động chậm hơn thực tế.
*   **Frame Delivery & Packet Loss:** Mạng Wifi có chênh lệch truyền tải (Jitter) và rớt gói tin. Nếu rớt gói I-Frame của thuật toán nén H264, màn hình sẽ bị "rách" và xuất hiện các khối xám (Mác Lỗi Artifact).
*   **Blocking Call:** Hàm `cap.read()` của Webcam dùng cáp trả về ngay lập tức. Nhưng `cap.read()` của IP Camera sẽ **đóng băng toàn bộ Thread** (Hanging) nếu mạng chập chờn và đang đợi tải tiếp.

---

## 2. Chiến Lược Xử Lý Frame (Frame Handling Strategy)

Để hệ thống hoạt động chính xác với mục tiêu **Safety First (An Toàn là Trên Hết)**, chúng ta buộc phải hy sinh tính tuần tự mượt mà của video để đổi lấy **Tính Thời Gian Thực tuyệt đối (Low-latency)**.

*   **Không xử lý tất cả frames (Drop frames proactively):** Không được phép bắt AI xử lý lần lượt từng frame nếu AI chạy chậm hơn tốc độ mạng đổ về. Nếu mạng đổi về 30 FPS, mà AI tiêu tốn 40ms/frame (25 FPS), việc bám đuổi từng frame sẽ kéo sập hệ thống do tràn RAM.
*   **Chiến lược Lật Trang (LIFO / Latest Frame Only):** Thiết lập một biến toàn cục `self.latest_frame`. Luồng Camera (Producer) liên tục đè dữ liệu mới nhất lên biến này. Luồng AI (Consumer) cứ xong việc cũ là sẽ "bốc" khung hình mới nhất trên biến đó ra chạy tiếp. Những frame cũ giữa đường bị ghi đè sẽ bị vứt bỏ hoàn toàn.
*   **Kích thước Buffer:** Mặc định phải là **1 (One)**. Nếu dùng Queue, giới hạn kích thước hàng đợi Queue = 1 để đẩy frame cũ ra nếu mạng nhồi thêm.

---

## 3. Khắc Phục Lỗi Giật Lag & Tích Lũy Delay 

OpenCV thường phớt lờ cấu hình `cv2.CAP_PROP_BUFFERSIZE = 1` đối với RTSP/HTTP. Để trị tận gốc:

**Sửa lỗi Code-level:**
1.  **Dùng biến toàn cục + Khóa Lock thay cho Queue:** Hàng đợi (Queue) có hàm `.get()` bị block nếu rỗng. Trong Computer vision, thay vì dùng Queue, thao tác Shared State (copy array numpy) bằng `threading.Lock` là cách tốt nhất để đảm bảo Không Bao Giờ bị Blocking.
2.  **RTSP FFmpeg parameters:** Khi dùng luồng RTSP, luôn ép OpenCV cấm bộ định tuyến TCP buffer.
    ```python
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp|fflags;nobuffer|flags;low_delay"
    ```

---

## 4. Mã Nguồn Mở Rộng: Universal Camera Source

Đoạn code refactor sạch luồng lấy hình (hỗ trợ cả USB Webcam lẫn RTSP stream), hoàn toàn không bị ngấm Lag:

```python
import cv2
import threading
import time
import os
import numpy as np

class UniversalVideoSource:
    def __init__(self, source_url):
        # Tắt cơ chế đệm mạng mặc định của FFmpeg để chống trễ (delay)
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "fflags;nobuffer|flags;low_delay"
        
        self.source_url = source_url
        self.cap = cv2.VideoCapture(self.source_url)
        
        # Ép phần cứng dùng Buffer=1 (Có tác dụng cực tốt trên Local Webcam)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        self.latest_frame = None
        self.is_running = True
        self.lock = threading.Lock()
        
        # Bật luồng Thu Nhận Hình Ảnh Ngầm (Daemon Thread)
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def _capture_loop(self):
        while self.is_running:
            # Lệnh này bị block nếu mạng nghẽn, nên phải đưa ra Thread riêng
            ret, frame = self.cap.read()
            if not ret:
                # Nếu rớt mạng, delay nhẹ rồi thử lại (Auto-reconnect giả lập)
                time.sleep(0.5) 
                continue
                
            with self.lock:
                self.latest_frame = frame.copy() # Lưu frame siêu thực mới nhất

    def get_latest_frame(self):
        """AI Worker sẽ gọi hàm này. Returns (is_valid, numpy_array)"""
        with self.lock:
            if self.latest_frame is None:
                return False, None
            return True, self.latest_frame.copy()

    def stop(self):
        self.is_running = False
        self.thread.join(timeout=1.0)
        self.cap.release()
```

---

## 5. Cải Thiện Độ Ổn Định (Stability Enhancements)

Nếu người dùng đang chạy livestream và bị ngắt kết nối tạm thời từ Wi-Fi của điện thoại:
1.  **Vá lưới thời gian (Frame Drops / Jitter):** 
    Nếu `get_latest_frame()` liên tục trả về chính xác cái frame cũ (vì Camera Thread bị kẹt), AI Worker có thể liên tục đánh giá hình ảnh bị đóng băng. **Giải pháp:** Lưu trữ giá trị `thời gian timestamp` của frame được gắn vào ảnh. Nếu qua 500ms mà không có frame mới, buộc hệ thống UI nhảy sang trạng thái cảnh báo **[NETWORK LOST]**.
2.  **Công cụ `MSE` của bộ tiền xử lý (Rách Hình/Tear):**
    Bộ xử lý MSE mà chúng ta vừa tích hợp (`MSE > 2000`) sinh ra chính xác cho việc này! RTSP Streaming rất dễ rớt các dải I-Frames tạo ra pixel vỡ nát. Chúng ta sẽ "Vứt thẳng" các frame có tỷ lệ rách hình cao mà k chạy YOLO, để tránh mô hình YOLO bị ảo giác (ảo giác do nhiễu pixel nén).
3.  **Tối ưu độ phân giải động (Dynamic Resolution):**
    Nếu FPS của luồng Camera Thread bị tuột dốc (< 10FPS), tiến hành dùng `cv2.resize()` thu ngay ảnh về khoảng `1280x720` xuống `640x480` trước khi nạp vào AI Thread, giúp CPU lấy lại nhịp độ.

---

## 6. Kiến Trúc Cuối Cùng Dành Cho Môi Trường Mạng (Final Architecture Flow)

Sơ đồ vận hành hoàn chỉnh 4 nhánh luồng của hệ thống sau khi cắm Mobile Camera (Webcam IP):

```text
[ Mobile IP Camera (RTSP/HTTP) ] 🌐 --- (Biến động 15~30 FPS, mạng delay)
          |
          V
[ 🧵 DEDICATED CAPTURE THREAD ] (Worker 1)
   1. Ngồi chờ mạng (có thể bị Block nếu nghẽn).
   2. Giải nén luồng H264 qua FFmpeg.
   3. Ghi đè khốc liệt ảnh vào Share.LATEST_FRAME (Drop Frame cũ vĩnh viễn).
          |
  (Lock & Copy) <-- Trạm trung chuyển không bao giờ bị nghẽn (Zero Wait)
          |
[ 🧵 HEAVY AI WORKER THREAD ] (Worker 2)
   1. Kéo LATEST_FRAME ra.
   2. Preprocessor: Đánh giá Rách Hình MJPEG (Bằng MSE) -> Rách thì VỨT để lấy frame sau.
   3. YOLOv8 TensorRT + Rule Engine.
   4. Cập nhật cảnh báo M-Score và Ghi đè vào Share.AI_RESULTS.
          |
  (Lock & Copy)
          |
[ 🧵 MAIN UI RENDER THREAD ] (Chạy chẵn 30FPS / Màn hình)
   1. Kéo LATEST_FRAME kết hợp với AI_RESULTS lên màn hình.
   2. Hệ thống hoàn toàn tách rời sự mượt mà của UI (<30ms) với sự chậm trễ của luồng IP Mạng (100ms+)!
```

**Sự thay đổi cốt lõi:** Luồng cắm mạng (RTSP) có thể thỉnh thoảng đứng hình 2 giây vì rớt mạng (Block Thread), nhưng màn hình quản lý UI (Main Thread) sẽ KHÔNG bị đứng hình, và luồng AI vẫn chạy bình thường. Chúng ta đã chia nhỏ mọi tác vụ rủi ro vào các giỏ khác nhau.
