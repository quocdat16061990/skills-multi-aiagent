# Invoice fields

Workbook luôn có đúng năm sheet: `Summary`, `Invoices`, `Attachments`, `Duplicates`, và `Review_Errors`.

## Invoice fields

- `source`: đường dẫn file đã tải hoặc giải nén, chỉ dùng số thứ tự nội bộ.
- `seller_name`, `seller_tax_id`: tên và mã số thuế bên bán.
- `buyer_name`, `buyer_tax_id`: tên và mã số thuế bên mua.
- `symbol`: ký hiệu hoặc series hóa đơn.
- `invoice_number`: số hóa đơn.
- `invoice_date`: ngày theo giá trị nguồn, không tự suy đoán định dạng khác.
- `payment_method`: hình thức thanh toán nếu có nhãn rõ ràng.
- `currency`: đơn vị tiền tệ từ nguồn hoặc `VND` khi chứng từ thể hiện ký hiệu đồng Việt Nam.
- `subtotal`, `tax_rate`, `tax`, `total`: chuỗi giá trị nguồn; không tự ép số theo locale.
- `confidence`: `high` khi có số hóa đơn, tổng tiền và mã số thuế bên bán hoặc ký hiệu; `medium` khi có ít nhất bốn trường; còn lại là `low`.
- `notes`: trường thiếu hoặc vấn đề cần rà soát.

File chỉ được ghi vào `Invoices` khi có khóa nhận diện đủ mạnh. Ảnh không OCR hoặc tài liệu không có trường nhận diện không được tính thành một hóa đơn giả.

## Attachment fields and privacy

Sheet `Attachments` chỉ lưu `message_index`, thời gian UTC, subject, sender, tên file, MIME type, kích thước, SHA-256 và đường dẫn đã lưu.

Không lưu hoặc hiển thị Gmail `message_id`, `thread_id` hay `attachment_id` trong stdout, workbook hoặc tên folder. Các ID này chỉ tồn tại tạm trong bộ nhớ để tải attachment.

## Deduplication

1. Attachment trùng byte được phát hiện bằng SHA-256.
2. Hóa đơn đã bóc tách được so bằng `seller_tax_id + invoice_number`; nếu thiếu mã số thuế bên bán thì dùng `symbol + invoice_number`.
3. Tài liệu chưa đọc được có thể được đánh dấu bản trùng mức `medium` khi subject chứa đúng số hóa đơn đã bóc tách và người gửi trùng khớp.

Không âm thầm gộp khóa yếu. Mọi bằng chứng trùng được giữ trong `Duplicates` cùng loại khóa và mức confidence.

## Safety and review

XML chứa `DOCTYPE` hoặc `ENTITY` bị từ chối trước khi parse bằng stdlib `ElementTree`. ZIP bị giới hạn số file, kích thước từng file, tổng kích thước giải nén, extension và path traversal. Chuỗi Excel bắt đầu bằng `=`, `+`, `-`, hoặc `@` được thêm apostrophe; workbook được mở lại để xác minh sau khi ghi.

Khoảng ngày Gmail dùng Unix timestamp theo timezone được chọn để tránh lệch ngày do timezone mặc định của Gmail search. Mặc định skill dùng `Asia/Ho_Chi_Minh`. Cả query và API request đều khóa nhãn `INBOX`; skill không đọc All Mail, Sent, Spam hoặc Trash.
