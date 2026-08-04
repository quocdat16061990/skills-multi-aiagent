# Schema Excel

Workbook có đúng 7 sheet:

1. `Tong_quan`: Nhóm, Chỉ số, Giá trị; chart phân bố chủ đề.
2. `Du_lieu_video`: channel/title/handle/subscribers; video ID/title/URL/views/date certainty/duration/type/views-day; topic/hook và evidence.
3. `Top_video`: hạng, ID, title, URL, views, type.
4. `Chu_de`: nhãn coding và số video.
5. `Hook_va_tieu_de`: hook coding, số video, ghi chú.
6. `De_xuat_hanh_dong`: loại phát biểu, đề xuất, bằng chứng, độ tin cậy.
7. `Nguon_va_gioi_han`: nguồn, timestamp, facts/coding/inference, cảnh báo và giới hạn.

Yêu cầu: header style, freeze hàng 1, autofilter, độ rộng cột hợp lý, URL hyperlink, ô số giữ kiểu numeric. Mọi chuỗi bắt đầu bằng `=`, `+`, `-`, `@` phải được prefix apostrophe trước khi ghi. Sau save phải reopen bằng `openpyxl` và xác nhận tên sheet/cột cốt lõi.
