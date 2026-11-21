# Beauty Box — công cụ crawl toàn bộ danh mục công khai

Ngày chuẩn bị: 19/11/2026.

## Trạng thái thực tế
Chưa crawl được toàn bộ dữ liệu trong môi trường thực hiện. API danh mục công khai trả HTTP 403 và thông báo CloudFront chặn truy cập từ quốc gia hiện tại. Trang Tất cả sản phẩm không cung cấp danh mục trong HTML ban đầu; trang thương hiệu không cung cấp các liên kết thương hiệu trong HTML đọc được. Sitemap kiểm tra có 59 URL, chỉ 1 URL dưới /products/ và đó là trang deal, không phải danh sách toàn bộ sản phẩm.

Gói này là mã chạy lại và notebook, KHÔNG phải bộ dữ liệu Beauty Box đầy đủ. Không đưa dữ liệu mẫu ngày 11/11/2026 vào để thay cho dữ liệu hiện tại. Khả năng phân trang toàn danh mục chưa được kiểm chứng trực tiếp do lỗi truy cập trên.

## Chạy trên máy của bạn
Dùng máy/mạng có thể truy cập hợp lệ website Beauty Box. Máy ở Việt Nam có thể có điều kiện truy cập khác môi trường thực hiện, nhưng không bảo đảm thành công. Kaggle/Colab cũng có thể bị giới hạn theo vị trí máy chủ.

```bash
python -m pip install lxml
python crawl_all_beautybox.py --output beautybox_current
```

Hoặc mở notebook BeautyBox_Crawl_All.ipynb trong Jupyter/Kaggle và chạy từng ô. Bật Internet nếu môi trường notebook yêu cầu.

Nếu bị ngắt giữa chừng, chạy tiếp cùng thư mục:

```bash
python crawl_all_beautybox.py --output beautybox_current --resume
```

Muốn lấy lại toàn bộ dữ liệu mới tại một thời điểm khác, dùng thư mục mới. --resume giữ các chi tiết đã tải trong lần chạy trước, không cập nhật lại chúng.

## Những gì mã thực hiện
1. Kiểm tra robots.txt của website.
2. Đọc danh mục qua giao diện client công khai của storefront, 40 sản phẩm/trang; dùng offset, total và loại trùng product_id. Không đọc dữ liệu tài khoản.
3. Nếu tổng thay đổi khi phân trang, số ID duy nhất khác total, tổng trả về 0 hoặc bị từ chối truy cập, ghi incomplete và dừng. Không tự coi kết quả rỗng là đã hoàn tất.
4. Đọc từng URL sản phẩm, lấy JSON công khai nhúng trong HTML và đối chiếu product_id với danh mục.
5. Lưu checkpoint theo sản phẩm, rồi xuất products.csv/json và variants.csv/json. Giá trị trống giữ nguyên; CSV dùng UTF-8 BOM.
6. Chỉ ghi status=complete khi đã kiểm tra đủ các ID trong danh mục và chi tiết. API có thể giới hạn danh mục trả về; complete ở đây là đầy đủ so với danh mục công khai mà API trả về, không gồm các bản ghi quản trị/ẩn không công khai.

## Các trường
Tên, mã sản phẩm, SKU, thương hiệu hiển thị nếu có, danh mục, nhãn xuất xứ gốc, nguồn gốc thương hiệu/nơi sản xuất nếu ghi rõ, dung tích/khối lượng trong tên, giá hiện tại và khoảng giá/giá trước giảm, công dụng, thành phần chính, thành phần đầy đủ nếu có nhãn, loại da/tóc, hướng dẫn dùng, mô tả văn bản được làm sạch HTML/CSS, ảnh, biến thể, mã vạch, tồn kho gốc, URL và thời gian thu thập.

Thông tin phân mục lấy theo nhãn và có thể chưa bao quát toàn bộ nội dung; description_text giữ phần mô tả văn bản để xử lý tiếp. details/*.json giữ cả đối tượng sản phẩm gốc. Không tự suy ra thương hiệu từ tên, nguồn gốc thương hiệu từ nhãn Xuất xứ hoặc nơi sản xuất từ thông tin quảng cáo. Danh sách thành phần chính không được coi là danh sách đầy đủ. Giá có thể có ở sản phẩm hết hàng; số tồn kho thô không đại diện toàn bộ hệ thống cửa hàng. Các claim công dụng là nội dung người bán, không được kiểm chứng độc lập.

## Giới hạn và kiểm tra
Mã dùng định dạng request công khai của frontend đã khảo sát trong cuộc hội thoại; website có thể đổi cấu trúc. Danh mục hoàn chỉnh, sơ đồ trường trả về của API và toàn bộ quá trình phân trang chưa thể chạy kiểm thử trực tiếp từ môi trường này. Vì vậy không cam kết notebook sẽ lấy được toàn bộ danh mục trước khi chạy trên một mạng được website cho phép.

Mã dừng ngay với HTTP 401/403/429; không dùng proxy, VPN, xoay IP, bỏ CAPTCHA hay dữ liệu đăng nhập. Khi gặp chặn truy cập, giữ kết quả đã tải và đọc status.json. Không chạy lặp để vượt giới hạn.

Tốc độ mặc định: tải tuần tự, nghỉ 1,5 giây mỗi lượt. Có timeout, thử lại hạn chế cho lỗi mạng/5xx. Thời gian toàn bộ phụ thuộc số sản phẩm và tốc độ tải. status.json ghi lỗi, số bản ghi và các ID còn thiếu; không nên coi file CSV tồn tại là bằng chứng đã crawl xong.
