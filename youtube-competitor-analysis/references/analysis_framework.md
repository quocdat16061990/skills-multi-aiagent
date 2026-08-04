# Khung phân tích

## 1. Phân tầng phát biểu

- **Fact**: title, video ID, URL, views, chuỗi ngày đăng, duration, metadata channel lấy trực tiếp từ nguồn công khai. Nếu thiếu ghi `N/A`, không nội suy.
- **Coding**: topic/hook do quy tắc deterministic trong config gán. Báo cáo phải lưu từ khóa hoặc đoạn regex khớp làm bằng chứng.
- **Inference**: đề xuất chiến thuật từ mẫu mô tả. Ghi bằng chứng, độ tin cậy; tránh ngôn ngữ nhân quả như “hook X làm tăng view”.

## 2. Chỉ số

Tính count, total, mean, median, min, max và top theo views cho toàn bộ, Shorts, long-form và unknown. Views/day = views / max(1, số ngày từ ngày đăng đến hôm nay), chỉ khi ngày ISO tuyệt đối được nguồn cung cấp và parse chắc chắn. Không chuyển “3 months ago” thành ngày giả.

## 3. Loại video

Ưu tiên dấu hiệu URL/renderer Shorts. Khi duration có sẵn: <=60 giây là Shorts, >60 giây là long-form. Nếu không đủ chứng cứ giữ `unknown`; không ép phân loại.

## 4. Diễn giải

So sánh trong cùng tập thu thập và nêu cỡ mẫu. Median hữu ích khi views lệch mạnh. Top video là quan sát lịch sử, không phải dự báo. Subscriber có thể ẩn/N/A. Collector HTML ban đầu có thể không lấy được continuation, vì vậy luôn công bố source và cảnh báo.
