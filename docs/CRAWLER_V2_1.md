# Beauty Box V2.1 — sửa lỗi chờ phân trang của V2

Ngày cập nhật: 19/11/2026. Tên thư mục vẫn là `BeautyBox_Browser_V2` để tương thích với bản đã tải.

## Thay đổi chính

V2 dùng `Page.expect_response` để chờ một URL API có collection và số trang khớp chính xác. Log người dùng cho thấy đã đọc được 40/97 sản phẩm và hai chi tiết, nhưng điều kiện chờ này timeout ở trang 2. Timeout không tự chứng minh máy/IP bị chặn. Ảnh không cho biết request đã thất bại hay đã đi qua một đường phản hồi khác.

Mã frontend công khai cho thấy trang collection điều hướng với **limit và offset**. V2.1 tải trực tiếp HTML collection theo `?limit=40&offset=40`, đọc JSON nhúng trong HTML rồi đối chiếu chính offset được trả về. Không còn đợi XHR hay phụ thuộc nút Next đã gắn sự kiện JavaScript hay chưa. `?page=2` trên URL HTML không có tác dụng phân trang trong lần khảo sát.

Mặc định dùng HTTP qua Python, không cần Chromium. Chế độ trình duyệt tùy chọn cũng mở trực tiếp URL có offset và không dùng `expect_response`.

Đã kiểm tra trực tiếp ba trang của `top-san-pham`: **40 + 40 + 17 = 97 ID duy nhất**, cùng total=97. Kết quả này chỉ xác nhận một collection, không phải tổng toàn website.

## Cập nhật từ V2 đã cài trên Mac

1. Tải lại ZIP mới và giải nén ra chỗ khác.
2. Từ thư mục vừa giải nén, chép đè **`crawl_all_beautybox.py`** vào thư mục `BeautyBox_Browser_V2` đang dùng. Không cần thay cả thư mục và không cần xóa kết quả cũ. File `beautybox_data.py` giữ nguyên tương thích.
3. Trong Terminal đang mở ở thư mục cũ, chạy:

```bash
./.venv/bin/python -u crawl_all_beautybox.py --check --output beautybox_check --resume
```

Lúc đầu phải hiện **`Beauty Box V2.1 | HTTP`**. Nếu vẫn hiện V2 thì chưa thay đúng file Python.

V2.1 kiểm tra mọi trang của một collection và hai chi tiết. Với dữ liệu lúc khảo sát, log là:

```text
  top-san-pham: 40/97 (trang 1)
  top-san-pham: 80/97 (trang 2)
  top-san-pham: 97/97 (trang 3)
```

Khi có `"status": "check_passed"`, chạy toàn bộ các collection tìm thấy:

```bash
./.venv/bin/python -u crawl_all_beautybox.py --output beautybox_browser --resume
```

Chạy lại đúng lệnh này để tiếp tục sau khi bị ngắt. Hai chi tiết cũ trong thư mục check được tái sử dụng khi `--resume`; danh mục bị lỗi được đọc lại từ trang 1. Hai sản phẩm trong chế độ check là chủ ý kiểm tra, không phải số sản phẩm tối đa chương trình lấy được.

Nếu cần vào lại đúng thư mục giống ảnh người dùng:

```bash
cd "$HOME/Downloads/BeautyBox_Crawl_All_Toolkit/BeautyBox_Browser_V2"
```

Nếu bạn giải nén ở vị trí khác, đổi dòng cd tương ứng.

## Cài mới trên Mac

Giải nén thư mục `BeautyBox_Browser_V2` vào Downloads, rồi chạy:

```bash
cd "$HOME/Downloads/BeautyBox_Browser_V2"
bash RUN_MAC.command check
bash RUN_MAC.command
```

Cần Python 3.10 trở lên và Internet. Script tạo môi trường Python và cài lxml. Không cần sudo, kích hoạt môi trường thủ công, tài khoản Beauty Box hay cài trình duyệt.

## Chạy thủ công / Windows

```bash
python -m pip install -r requirements.txt
python crawl_all_beautybox.py --check --output beautybox_check
python crawl_all_beautybox.py --output beautybox_browser
python crawl_all_beautybox.py --output beautybox_browser --resume
```

Nếu HTTPS gặp lỗi chứng chỉ hoặc Python không tải được HTML dù trình duyệt thường mở được, có thể chọn transport trình duyệt. Không tắt xác minh chứng chỉ:

```bash
python -m pip install -r requirements-browser.txt
python -m playwright install chromium
python crawl_all_beautybox.py --transport browser --check --output beautybox_check --resume
```

Với V2 đã cài Playwright, có thể dùng ngay:

```bash
./.venv/bin/python -u crawl_all_beautybox.py --transport browser --check --output beautybox_check --resume
```

Đây là lựa chọn thủ công khi HTTP gặp lỗi môi trường; chương trình không tự đổi phương thức khi bị từ chối truy cập. HTTP 401/403/429 sẽ dừng và giữ checkpoint.

## Cách thu thập

1. Đọc robots.txt, trang chủ, thương hiệu và menu CMS công khai để tìm collection thật.
2. Đọc trang đầu từng collection, chỉ lấy truy vấn có đúng slug; không dùng sản phẩm gợi ý thay danh mục.
3. Đọc URL HTML với offset bằng số sản phẩm đã lấy. Xác nhận offset trong truy vấn nhúng khớp yêu cầu; kiểm tra total ổn định và không lặp ID. Không gọi trực tiếp API client.
4. Hợp nhất product_id rồi đọc trang chi tiết. Lấy SKU, tên, thương hiệu hiển thị, giá, mô tả, công dụng/thành phần/loại da/cách dùng nếu có nhãn, ảnh và biến thể.
5. Lưu checkpoint từng sản phẩm; xuất CSV UTF-8 BOM sau sản phẩm đầu tiên, mỗi 10 sản phẩm và khi dừng/kết thúc.

Tải tuần tự, mặc định tối thiểu hai giây giữa các trang. Không dùng proxy, xoay IP, stealth, giải CAPTCHA hay đăng nhập tự động.

## Đọc kết quả

| File | Nội dung |
|---|---|
| `products.csv`, `products.json` | Chi tiết từng sản phẩm |
| `variants.csv`, `variants.json` | Biến thể, SKU/mã vạch, giá, tồn kho thô |
| `details/*.json` | Checkpoint chi tiết và đối tượng sản phẩm gốc |
| `catalog.json` | Các ID tìm thấy và collection nguồn |
| `collections_report.csv` | Total, số ID, số trang, trạng thái/lỗi từng collection |
| `collections/*.json` | Checkpoint danh mục |
| `status.json` | Tổng kết, ID còn thiếu và lỗi |
| `last_page.html` | Trang cuối nếu dừng vì lỗi toàn lượt chạy |

`check_passed`: đã đọc đủ mọi trang của collection kiểm tra và đủ hai chi tiết được chọn. Các chi tiết khác được đếm trong `intentionally_skipped_details`, không coi là thiếu do lỗi.

`finished_discovered_scope`: đã đọc đủ phân trang các collection tìm thấy và chi tiết của các ID đó. Chưa có tổng chuẩn toàn website để chứng minh bao phủ 100%, nên `full_site_verified` vẫn là false.

`check_failed`/`incomplete`: xem errors, failed_collections và collections_report.csv. V2.1 cũng đưa lỗi collection vào errors, tránh trường hợp errors rỗng nhưng phân trang đã lỗi.

Các collection trả 0 được liệt kê riêng: có thể thật sự rỗng, đã bỏ hoặc truy vấn có vấn đề. Không suy diễn xuất xứ/công dụng/thành phần khi thiếu; giữ mô tả đầy đủ và giá trị trống để xử lý sau.

`--resume` giữ chi tiết đã lưu, không tự cập nhật giá cũ. Dùng tên thư mục mới cho một đợt thu thập mới.

Tài liệu liên quan: https://beautybox.com.vn/collections/top-san-pham và https://playwright.dev/python/docs/api/class-page#page-expect-response .
