# Dữ liệu và các giai đoạn xử lý

## Dữ liệu crawl gốc

`data/raw/beautybox_browser.zip` giữ nguyên các bản ghi của thư mục `beautybox_browser/` đã cung cấp. Chỉ bỏ metadata Finder (`.DS_Store`, `__MACOSX`, resource fork); không sửa giá trị dữ liệu hay trạng thái crawl.

| File bên trong ZIP | Ý nghĩa |
|---|---|
| `products.csv`, `products.json` | 1.086 chi tiết sản phẩm đã đọc được |
| `variants.csv`, `variants.json` | 2.533 biến thể thuộc các chi tiết đó |
| `catalog.json` | 1.130 ID phát hiện được và collection nguồn |
| `details/*.json` | Checkpoint từng sản phẩm và đối tượng gốc |
| `collections/*.json` | Phân trang và trạng thái từng collection |
| `collections_report.csv` | Báo cáo collection |
| `discovery.json` | Các collection đã phát hiện |
| `run_config.json` | Cấu hình lượt chạy |
| `status.json` | Trạng thái, lỗi, các ID thiếu |

Lượt chạy gốc có 83 collection được xử lý: 67 hoàn tất và có sản phẩm, 1 trả rỗng, 15 lỗi. Trạng thái `incomplete` và `full_site_verified=false` được giữ nguyên. Các số này thuộc snapshot 19/11/2026.

## Bản Excel đã xử lý

`BeautyBox_Tat_Ca_Ket_Qua.xlsx` là bản tổng hợp trước các lần chỉnh sửa tiếp theo. `em_iu_beautybox_rut_gon.xlsx` là bản cuối đã bổ sung thông tin, thêm kết cấu và rút gọn nội dung. Bản cuối có 3.788 hàng dữ liệu trong sheet `Tất cả`: 1.130 hàng sản phẩm và 2.658 hàng biến thể.

| Cột | Ý nghĩa |
|---|---|
| `Danh mục` | Danh mục sản phẩm |
| `Loại dòng` | Sản phẩm hoặc biến thể |
| `ID sản phẩm`, `SKU` | Khóa để đối chiếu; nên giữ dạng chuỗi |
| `Tên sản phẩm`, `Thương hiệu` | Thông tin nhận diện |
| `Xuất xứ thương hiệu` | Nguồn gốc thương hiệu theo thông tin có sẵn |
| `Giá` | Giá đã ghi nhận, không đảm bảo còn hiệu lực |
| `Đối tượng`, `Dung tích`, `Kết cấu` | Đặc tính sản phẩm |
| `Công dụng` | Ý chính được rút gọn thành các cụm ngắn |
| `Thành phần` | Ưu tiên chiết xuất, thảo dược, vitamin, khoáng chất và hoạt chất quen thuộc |
| `Mô tả đầy đủ` | Nội dung dài để đối chiếu |
| `URL ảnh gốc`, `URL ảnh biến thể`, `URL sản phẩm` | Các liên kết nguồn có sẵn |
| `Check` | Cột đánh dấu trong file làm việc |

Không tự coi một hàng sản phẩm là một biến thể bổ sung. Một số thông tin dùng chung giữa sản phẩm và biến thể; các giá trị riêng đã có được giữ theo từng hàng. Ô trống thể hiện thiếu thông tin hoặc không có nội dung phù hợp để giữ lại sau rút gọn, không có nghĩa là sản phẩm chắc chắn không chứa thành phần đó hay không có công dụng đó.

## Tư liệu đối chiếu

`data/sources/BeautyBox_Nguon_Doi_Chieu_20261120.zip` là tư liệu đã lưu cho bước đối chiếu/bổ sung ngày 20/11/2026. Các kết quả Excel không chỉ là bản đổi định dạng CSV từ snapshot gốc; chúng còn có các bước làm sạch, bổ sung và chỉnh sửa riêng.

File Hasaki được dùng để tham khảo phong cách viết, không được đưa vào dataset Beauty Box trong gói này.
