# Beauty Box Crawler & Product Dataset

Thu thập danh mục và chi tiết sản phẩm công khai từ Beauty Box, tách biến thể, lưu checkpoint và xuất CSV/JSON. Repository kèm dữ liệu đã thu thập cùng các bản Excel đã tổng hợp và chuẩn hóa.

Mã chính là **V2.1**, đọc HTML công khai và phân trang bằng `limit`/`offset`. Chế độ mặc định dùng HTTP; Playwright là tùy chọn. Cần Python 3.10 trở lên.

## Nội dung

| Đường dẫn | Nội dung |
|---|---|
| `crawl_all_beautybox.py` | Khám phá collection, phân trang, đọc chi tiết, lưu và tiếp tục crawl |
| `beautybox_data.py` | Phân tích dữ liệu sản phẩm và biến thể nhúng trong trang |
| `requirements.txt` | Thư viện cho chế độ HTTP |
| `requirements-browser.txt` | Thư viện bổ sung cho chế độ trình duyệt |
| `RUN_MAC.command` | Tạo môi trường và chạy trên macOS |
| `data/raw/beautybox_browser.zip` | Toàn bộ kết quả crawl gốc, CSV/JSON, checkpoint và báo cáo trạng thái |
| `data/processed/BeautyBox_Tat_Ca_Ket_Qua.xlsx` | Bản Excel tổng hợp trước các bước chỉnh sửa sau đó |
| `data/processed/em_iu_beautybox_rut_gon.xlsx` | Bản Excel đã bổ sung và rút gọn thông tin; sheet `Tất cả` |
| `data/sources/BeautyBox_Nguon_Doi_Chieu_20261120.zip` | Tư liệu đã dùng để đối chiếu và bổ sung dữ liệu |
| `docs/` | Hướng dẫn chi tiết, mô tả dữ liệu và kết quả kiểm tra đã lưu |
| `tests/` | 15 kiểm tra hồi quy ngoại tuyến với HTML đã lưu |
| `legacy/api/` | Bản API cũ cùng notebook và thông tin lỗi truy cập để tham khảo |

Các tập dữ liệu nguồn được giữ dưới dạng ZIP để repository gọn và không phải theo dõi hàng nghìn checkpoint riêng lẻ.

## Chạy trên macOS / Linux

Mở Terminal tại thư mục repository:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python crawl_all_beautybox.py --check --output data/runs/check
```

Sau khi kiểm tra thành công, chạy thu thập các danh mục tìm thấy:

```bash
./.venv/bin/python crawl_all_beautybox.py --output data/runs/beautybox
```

Chạy tiếp cùng lượt nếu bị ngắt:

```bash
./.venv/bin/python crawl_all_beautybox.py --output data/runs/beautybox --resume
```

Trên macOS cũng có thể dùng `bash RUN_MAC.command check`, sau đó `bash RUN_MAC.command`. Hai lệnh này lưu ở `beautybox_check/` và `beautybox_browser/` ngay trong repository.

## Chạy trên Windows (PowerShell)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe crawl_all_beautybox.py --check --output data/runs/check
.\.venv\Scripts\python.exe crawl_all_beautybox.py --output data/runs/beautybox
```

Để tiếp tục, thêm `--resume` và giữ nguyên `--output`. Dùng thư mục mới nếu muốn thu thập lại giá và dữ liệu tại thời điểm khác.

## Chế độ trình duyệt tùy chọn

Sau khi tạo môi trường Python, cài thêm thư viện và Chromium:

```bash
./.venv/bin/python -m pip install -r requirements-browser.txt
./.venv/bin/python -m playwright install chromium
./.venv/bin/python crawl_all_beautybox.py --transport browser --check --output data/runs/browser_check
```

Trên Windows thay `./.venv/bin/python` bằng `.\.venv\Scripts\python.exe`. Xem các lựa chọn bằng `python crawl_all_beautybox.py --help`.

## Đọc dữ liệu có sẵn

Mở trực tiếp `data/processed/em_iu_beautybox_rut_gon.xlsx` để sử dụng bản đã xử lý. Các hàng sản phẩm và biến thể nằm gần nhau; danh mục được giữ ở cột riêng. Hai cột `Công dụng` và `Thành phần` đã được rút gọn, còn `Mô tả đầy đủ` được giữ để đối chiếu.

Muốn xem dữ liệu gốc hoặc dùng checkpoint cũ:

```bash
python -m zipfile -e data/raw/beautybox_browser.zip data/runs
```

Kết quả nằm trong `data/runs/beautybox_browser/`. Sau đó có thể tiếp tục bằng `--output data/runs/beautybox_browser --resume`.

Crawler tự xuất CSV/JSON; các bước bổ sung qua URL, chuẩn hóa nội dung và chỉnh sửa Excel đã được thực hiện riêng. Lệnh crawl không tự tái tạo toàn bộ bản Excel đã xử lý.

## Phạm vi dữ liệu

Snapshot gốc ngày 19/11/2026 chứa **1.086 chi tiết sản phẩm và 2.533 biến thể**, trong khi danh mục phát hiện **1.130 ID sản phẩm**. Trạng thái được lưu là `incomplete`: còn 44 chi tiết thiếu và 15 collection lỗi. Đây là kết quả của lượt chạy đã lưu, không phải số lượng hiện tại của website.

Bản Excel đã xử lý có **1.130 hàng sản phẩm và 2.658 hàng biến thể** sau các bước tổng hợp, bổ sung và chỉnh sửa. Vì hai tập ở hai giai đoạn khác nhau nên số lượng không trùng nhau. Xem [mô tả dữ liệu](docs/DATA.md).

`finished_discovered_scope` chỉ xác nhận đã đọc đủ phạm vi collection tìm được; chưa có tổng chuẩn toàn website để chứng minh bao phủ 100%. `--check` chỉ kiểm tra một collection và hai chi tiết. Crawler lưu trạng thái/checkpoint khi lỗi, dừng với 401/403/429 hoặc yêu cầu xác minh; không dùng xoay IP hay vượt CAPTCHA.

## Kiểm tra mã

Sau khi cài `requirements.txt`:

```bash
python -m unittest discover -s tests -v
```
