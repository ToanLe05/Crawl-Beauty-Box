"""Beauty Box V2.1: paginate public collection HTML with limit and offset.

Python 3.10+. Default transport: HTTP; optional isolated Chromium browser.
No direct client API, API signing, account, cookies or profile are required.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
import urllib.robotparser
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path

from lxml import html
from beautybox_data import now, parse_product

SITE = "https://beautybox.com.vn"
HOST = "beautybox.com.vn"
API_HOST = "beautybox-api.hsv-tech.io"
CHECK_COLLECTION = SITE + "/collections/top-san-pham"


class AccessBlocked(RuntimeError):
    pass


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def load(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def canonical_url(value, kind):
    if not isinstance(value, str):
        return None
    parsed = urllib.parse.urlsplit(urllib.parse.urljoin(SITE, value.strip()))
    if parsed.scheme != "https" or parsed.hostname != HOST:
        return None
    path = urllib.parse.unquote(parsed.path).strip().rstrip("/")
    if not re.fullmatch(r"/" + kind + r"/[A-Za-z0-9_-]+", path):
        return None
    return SITE + path


def page_state(markup):
    tree = html.fromstring(markup)
    nodes = tree.xpath('//script[@id="__NEXT_DATA__"]/text()')
    if not nodes:
        raise ValueError("Không tìm thấy __NEXT_DATA__: cấu trúc trang đã thay đổi.")
    data = json.loads(nodes[0])
    return tree, data.get("props", {}).get("pageProps", {}).get("initialReduxState", {})


def discover(markup):
    """Use actual links and public CMS/menu data, not guessed brand names."""
    tree, state = page_state(markup)
    strings = list(tree.xpath('//a/@href'))

    def walk(value):
        if isinstance(value, str):
            strings.extend(re.findall(
                r'(?:https://beautybox\.com\.vn)?/(?:collections|products)/[A-Za-z0-9_-]+', value))
        elif isinstance(value, dict):
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    # Menus contain subcategories which do not have an <a> in initial HTML.
    walk(state.get("cmsApi", {}).get("queries", {}))
    collections = {u for value in strings if (u := canonical_url(value, "collections"))}
    products = {u for value in strings if (u := canonical_url(value, "products"))}
    return collections, products


def catalog_payload(value):
    if not isinstance(value, dict) or not isinstance(value.get("data"), list):
        raise ValueError("Phản hồi danh mục không có data dạng danh sách.")
    total = value.get("total")
    if isinstance(total, bool) or not isinstance(total, (int, float)) or int(total) != total or total < 0:
        raise ValueError("Phản hồi danh mục thiếu total hợp lệ.")
    rows = value["data"]
    ids = []
    for row in rows:
        if not isinstance(row, dict) or row.get("id") is None or not row.get("slug"):
            raise ValueError("Bản ghi danh mục thiếu id/slug.")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", str(row["id"])):
            raise ValueError("ID sản phẩm không hợp lệ.")
        if not canonical_url("/products/" + row["slug"], "products"):
            raise ValueError("Slug sản phẩm không hợp lệ.")
        ids.append(str(row["id"]))
    if len(ids) != len(set(ids)) or len(rows) > total:
        raise ValueError("Danh sách có ID trùng hoặc số dòng vượt total.")
    return int(total), rows


def initial_listing(markup, slug, expected_offset=None):
    _, state = page_state(markup)
    for key, query in state.get("productsApi", {}).get("queries", {}).items():
        if not key.startswith("getAllProducts("):
            continue
        args = json.loads(key[key.index("(") + 1:-1])
        if args.get("data", {}).get("collections") == slug:
            if expected_offset is not None:
                try:
                    actual_offset = int(args.get("data", {}).get("offset", 0))
                except (TypeError, ValueError):
                    continue
                if actual_offset != expected_offset:
                    continue
            total, rows = catalog_payload(query.get("data"))
            return total, rows
    raise ValueError(f"Không tìm thấy danh mục đúng slug/offset ({slug}, offset={expected_offset}); không dùng trang đầu hoặc sản phẩm gợi ý thay thế.")


def merge_page(existing, rows, declared, page_total):
    if page_total != declared:
        raise ValueError(f"Tổng sản phẩm đổi trong lúc phân trang: {declared} → {page_total}.")
    old_ids = {str(x["id"]) for x in existing}
    new_ids = {str(x["id"]) for x in rows}
    if not rows or old_ids & new_ids:
        raise ValueError("Trang rỗng hoặc lặp ID: dừng danh mục để tránh báo đủ sai.")
    if len(existing) + len(rows) > declared:
        raise ValueError("Số ID duy nhất vượt tổng danh mục.")
    return existing + rows


def raise_http(status, url):
    if status in (401, 403, 429):
        raise AccessBlocked(f"HTTP {status}: {url}. Đã lưu checkpoint; dừng lượt chạy.")
    if status >= 400:
        raise RuntimeError(f"HTTP {status}: {url}")


class DocumentPagination:
    def next_page(self, slug, page_number, *, offset):
        # The storefront router uses offset, not ?page=2 on the document URL.
        # Fetch the document directly: no dependency on React hydration, XHR
        # request names, or whether Next.js uses its own /_next/data route.
        url = canonical_url("/collections/" + slug, "collections")
        if url is None or not isinstance(offset, int) or offset <= 0:
            raise ValueError("Slug/offset phân trang không hợp lệ.")
        url += "?" + urllib.parse.urlencode({"limit": 40, "offset": offset})
        return initial_listing(self.navigate(url), slug, expected_offset=offset)


class HttpReader(DocumentPagination):
    def __init__(self, delay, timeout):
        self.delay, self.timeout = delay, timeout / 1000
        self.last_request = 0.0
        self.robots = None
        self.last_html = None
        self.last_url = None

    def fetch(self, url):
        remaining = self.delay - (time.monotonic() - self.last_request)
        if remaining > 0:
            time.sleep(remaining)
        self.last_request = time.monotonic()
        self.last_url = url
        request = urllib.request.Request(url, headers={
            "User-Agent": "BeautyBoxDatasetResearch/2.1",
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.5",
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
        })
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raise_http(response.status, response.url)
                data = response.read().decode(response.headers.get_content_charset() or "utf-8")
                self.last_html = data
        except urllib.error.HTTPError as exc:
            self.last_html = exc.read().decode("utf-8", errors="replace")
            raise_http(exc.code, url)
            raise
        return data

    def setup_robots(self):
        self.robots = urllib.robotparser.RobotFileParser()
        self.robots.parse(self.fetch(SITE + "/robots.txt").splitlines())
        crawl_delay = self.robots.crawl_delay("BeautyBoxDatasetResearch")
        if crawl_delay:
            self.delay = max(self.delay, crawl_delay)

    def navigate(self, url):
        if self.robots is None or not self.robots.can_fetch("BeautyBoxDatasetResearch", url):
            raise AccessBlocked("robots.txt không cho phép đọc " + url)
        markup = self.fetch(url)
        # Check actual visible body text, not JavaScript which may mention CAPTCHA.
        tree = html.fromstring(markup)
        for element in tree.xpath("//script|//style|//noscript"):
            element.drop_tree()
        if re.search(r"verify (?:that )?you(?: are|'re) human|checking your browser|access denied|captcha", tree.text_content(), re.I):
            raise AccessBlocked("Website yêu cầu xác minh hoặc từ chối truy cập: " + url)
        page_state(markup)
        return markup


class BrowserReader(DocumentPagination):
    def __init__(self, page, delay, timeout):
        self.page, self.delay, self.timeout = page, delay, timeout
        self.last_request = 0.0
        self.robots = None
        self.denials = []
        page.on("response", self.on_response)

    def on_response(self, response):
        # Only a denied document/catalog/product request blocks this crawler.
        parsed = urllib.parse.urlsplit(response.url)
        relevant = (parsed.hostname == HOST and response.request.resource_type == "document") or (
            parsed.hostname == API_HOST and parsed.path.startswith("/client/products"))
        if relevant and response.status in (401, 403, 429):
            self.denials.append((response.status, response.url))

    def check_denials(self):
        if self.denials:
            status, url = self.denials[0]
            raise_http(status, url)

    def pause(self):
        self.page.wait_for_timeout(max(0, self.delay - (time.monotonic() - self.last_request)) * 1000)
        self.last_request = time.monotonic()
        self.check_denials()

    def setup_robots(self):
        self.pause()
        response = self.page.goto(SITE + "/robots.txt", wait_until="domcontentloaded", timeout=self.timeout)
        if response is None:
            raise RuntimeError("Không nhận được robots.txt.")
        raise_http(response.status, response.url)
        self.robots = urllib.robotparser.RobotFileParser()
        self.robots.parse(response.text().splitlines())
        crawl_delay = self.robots.crawl_delay("BeautyBoxDatasetResearch")
        if crawl_delay:
            self.delay = max(self.delay, crawl_delay)

    def navigate(self, url):
        if self.robots is None or not self.robots.can_fetch("BeautyBoxDatasetResearch", url):
            raise AccessBlocked("robots.txt không cho phép đọc " + url)
        self.pause()
        response = self.page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
        if response is None:
            raise RuntimeError("Không nhận được HTML: " + url)
        raise_http(response.status, response.url)
        visible_text = self.page.locator("body").inner_text(timeout=self.timeout)
        if re.search(r"verify (?:that )?you(?: are|'re) human|checking your browser|access denied|captcha", visible_text, re.I):
            raise AccessBlocked("Website yêu cầu xác minh hoặc từ chối truy cập: " + url)
        # Let normal hydration finish; the initial JSON itself is already in the HTML.
        self.page.locator("#__NEXT_DATA__").wait_for(state="attached", timeout=self.timeout)
        self.check_denials()
        markup = self.page.content()
        return markup

def collection_file(out, url):
    return out / "collections" / (url.rsplit("/", 1)[-1] + ".json")


def crawl_collection(reader, out, url, page_limit=None):
    slug = url.rsplit("/", 1)[-1]
    record = {"url": url, "slug": slug, "status": "incomplete", "started_at_utc": now(),
              "declared_total": None, "pages_read": 0, "items": [], "error": None}
    found_collections, found_products = set(), set()
    try:
        markup = reader.navigate(url)
        found_collections, found_products = discover(markup)
        total, rows = initial_listing(markup, slug)
        record.update(declared_total=total, pages_read=1, items=rows)
        save(collection_file(out, url), record)
        print(f"  {slug}: {len(rows)}/{total} (trang 1)", flush=True)
        if total == 0:
            record["status"] = "zero_result"
        else:
            page_number = 1
            while len(record["items"]) < total:
                if page_limit and page_number >= page_limit:
                    record["status"] = "limited_check"
                    break
                page_number += 1
                page_total, new_rows = reader.next_page(slug, page_number, offset=len(record["items"]))
                record["items"] = merge_page(record["items"], new_rows, total, page_total)
                record["pages_read"] = page_number
                save(collection_file(out, url), record)
                print(f"  {slug}: {len(record['items'])}/{total} (trang {page_number})", flush=True)
            else:
                record["status"] = "complete"
    except Exception as exc:
        record["error"] = str(exc)
        if isinstance(exc, AccessBlocked):
            record["status"] = "access_blocked"
            raise
        record["status"] = "error"
        print(f"  LỖI {slug}: {exc}", flush=True)
    finally:
        record["unique_count"] = len(record["items"])
        record["finished_at_utc"] = now()
        save(collection_file(out, url), record)
    return record, found_collections, found_products


def catalog_from_records(records, strict=True):
    items, sources = {}, {}
    for record in records:
        for row in record["items"]:
            pid = str(row["id"])
            if pid in items and items[pid]["slug"] != row["slug"]:
                if strict:
                    raise ValueError(f"ID {pid} có hai slug khác nhau; cần kiểm tra lại.")
                continue
            items[pid] = row
            sources.setdefault(pid, set()).add(record["url"])
    return items, sources


def write_csv(path, rows):
    if not rows:
        path.unlink(missing_ok=True)
        return
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                             for k, v in row.items()})


def summarize(out, records, queue, attempted, errors, check=False):
    try:
        items, sources = catalog_from_records(records)
    except ValueError as exc:
        error = {"error": str(exc), "type": "catalog_conflict"}
        if error not in errors:
            errors.append(error)
        items, sources = catalog_from_records(records, strict=False)
    snapshots = [load(p) for p in sorted((out / "details").glob("*.json"))]
    products = [s["product"] for s in snapshots]
    variants = [v for s in snapshots for v in s["variants"]]
    for name, rows in [("products", products), ("variants", variants)]:
        save(out / (name + ".json"), rows)
        write_csv(out / (name + ".csv"), rows)
    report = [{k: v for k, v in r.items() if k != "items"} for r in records]
    write_csv(out / "collections_report.csv", report)
    save(out / "catalog.json", {"items": list(items.values()),
                                "source_collections": {k: sorted(v) for k, v in sources.items()}})
    actual = {str(p["product_id"]) for p in products}
    expected_details = set(list(items)[:2]) if check else set(items)
    failed = [r["url"] for r in records if r["status"] not in ("complete", "zero_result")]
    zero = [r["url"] for r in records if r["status"] == "zero_result"]
    remaining = sorted(set(queue) - set(attempted))
    scope_ok = bool(items) and not failed and not remaining and not errors
    detail_ok = bool(items) and set(items) <= actual
    if check:
        check_ok = (any(r["pages_read"] >= 2 and r["status"] == "complete" for r in records)
                    and len(expected_details) == 2 and expected_details <= actual and not errors)
        state = "check_passed" if check_ok else "check_failed"
    else:
        state = "finished_discovered_scope" if scope_ok and detail_ok else "incomplete"
    collection_errors = [{"collection_url": r["url"], "error": r["error"]}
                         for r in records if r.get("error")]
    status = {"status": state, "updated_at_utc": now(), "version": "2.1", "mode": "public_html_offset",
              "transport": load(out / "run_config.json", {}).get("transport", "http"),
              "full_site_verified": False,
              "coverage_note": "Quét các danh mục tìm thấy qua menu, thương hiệu và liên kết công khai. Không có tổng chuẩn toàn website để chứng minh bao phủ 100%.",
              "discovered_collections": len(queue), "processed_collections": len(records),
              "nonempty_collections_complete": sum(r["status"] == "complete" for r in records),
              "zero_result_collections": zero, "failed_collections": failed,
              "remaining_collections": remaining, "known_catalog_products": len(items),
              "exported_products": len(products), "exported_variants": len(variants),
              "expected_detail_products": len(expected_details),
              "intentionally_skipped_details": len(items) - len(expected_details),
              "missing_product_ids": sorted(expected_details - actual), "errors": errors + collection_errors}
    save(out / "status.json", status)
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="Thư mục kết quả; luôn chỉ rõ khi --resume.")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--check", action="store_true", help="Kiểm tra mọi trang của một danh mục và 2 chi tiết, không phải toàn website.")
    parser.add_argument("--seed", action="append", default=[], help="Thêm URL danh mục công khai.")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--channel", choices=["chrome", "msedge"], default=None)
    parser.add_argument("--transport", choices=["http", "browser"], default="http")
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--timeout", type=int, default=60000, help="Milliseconds.")
    args = parser.parse_args()
    if args.delay < 1 or args.timeout < 1000:
        parser.error("--delay phải ≥1 giây và --timeout phải ≥1000 ms.")
    if args.resume and not args.output:
        parser.error("--resume cần --output để tiếp tục đúng thư mục cũ.")
    if any(not canonical_url(url, "collections") for url in args.seed):
        parser.error("--seed cần URL https://beautybox.com.vn/collections/<slug> hợp lệ.")
    out = Path(args.output or ("beautybox_check_" if args.check else "beautybox_browser_") + datetime.now().strftime("%Y%m%d_%H%M%S")).resolve()
    if out.exists() and any(out.iterdir()) and not args.resume:
        parser.error("Thư mục đã có dữ liệu. Dùng tên mới hoặc --output <tên cũ> --resume.")
    out.mkdir(parents=True, exist_ok=True)
    (out / "details").mkdir(exist_ok=True)
    previous = load(out / "run_config.json")
    if previous and bool(previous.get("check")) != args.check:
        parser.error("Không trộn thư mục kiểm tra với thư mục crawl đầy đủ.")
    save(out / "run_config.json", {"version": "2.1", "transport": args.transport,
                                  "check": args.check, "seeds": args.seed, "started_at_utc": now()})
    queue = [CHECK_COLLECTION] if args.check else load(out / "discovery.json", {}).get("collections", [])
    queue = list(dict.fromkeys(queue + [canonical_url(u, "collections") for u in args.seed]))
    records, attempted, errors = [], [], []
    browser = None
    page = None
    reader = None
    status = None
    print(f"Beauty Box V2.1 | {args.transport.upper()} | Output:", out, flush=True)
    try:
        with ExitStack() as stack:
            try:
                if args.transport == "http":
                    reader = HttpReader(args.delay, args.timeout)
                else:
                    from playwright.sync_api import sync_playwright
                    pw = stack.enter_context(sync_playwright())
                    options = {"headless": args.headless}
                    if args.channel:
                        options["channel"] = args.channel
                    browser = pw.chromium.launch(**options)
                    context = browser.new_context(locale="vi-VN", viewport={"width": 1365, "height": 900})
                    page = context.new_page()
                    page.set_default_timeout(args.timeout)
                    reader = BrowserReader(page, args.delay, args.timeout)
                reader.setup_robots()
                if not args.check:
                    for root in [SITE + "/", SITE + "/brands"]:
                        print("Khám phá:", root, flush=True)
                        markup = reader.navigate(root)
                        collections, _ = discover(markup)
                        queue = list(dict.fromkeys(queue + sorted(collections)))
                    # A verified public collection provides an early pagination check.
                    queue = list(dict.fromkeys([CHECK_COLLECTION] + queue))
                print(f"Đã tìm thấy {len(queue)} danh mục; bắt đầu phân trang.", flush=True)
                index = 0
                while index < len(queue):
                    url = queue[index]
                    index += 1
                    attempted.append(url)
                    checkpoint = load(collection_file(out, url)) if args.resume else None
                    if checkpoint and checkpoint.get("status") == "complete" and not args.check:
                        record = checkpoint
                        new_collections = set(checkpoint.get("discovered_collections", []))
                        print(f"Dùng checkpoint {record['slug']}: {len(record['items'])} sản phẩm", flush=True)
                    else:
                        record, new_collections, _ = crawl_collection(reader, out, url)
                    if not args.check:
                        queue = list(dict.fromkeys(queue + sorted(new_collections)))
                    record["discovered_collections"] = sorted(new_collections)
                    save(collection_file(out, url), record)
                    records.append(record)
                    save(out / "discovery.json", {"collections": queue, "updated_at_utc": now()})
                    summarize(out, records, queue, attempted, errors, args.check)
                items, sources = catalog_from_records(records)
                if not items:
                    raise ValueError("Không tìm thấy sản phẩm. Xem collections_report.csv; không coi 0 là đã xong.")
                selected = list(items.values())[:2] if args.check else list(items.values())
                print(f"Đọc chi tiết {len(selected)} sản phẩm; lưu checkpoint từng sản phẩm, cập nhật CSV mỗi 10.", flush=True)
                for i, item in enumerate(selected, 1):
                    pid = str(item["id"])
                    checkpoint = out / "details" / (pid + ".json")
                    if args.resume and checkpoint.exists():
                        continue
                    url = SITE + "/products/" + item["slug"]
                    try:
                        snapshot = parse_product(reader.navigate(url), url)
                        if snapshot["product"]["product_id"] != pid:
                            raise ValueError("ID danh mục và chi tiết không khớp.")
                        snapshot["product"]["source_collections"] = sorted(sources[pid])
                        save(checkpoint, snapshot)
                        print(f"Chi tiết {i}/{len(selected)}: {snapshot['product']['name']}", flush=True)
                    except AccessBlocked:
                        raise
                    except Exception as exc:
                        errors.append({"product_id": pid, "url": url, "error": str(exc)})
                        print(f"LỖI chi tiết {pid}: {exc}", flush=True)
                    if i == 1 or i % 10 == 0 or i == len(selected):
                        summarize(out, records, queue, attempted, errors, args.check)
            except (Exception, KeyboardInterrupt) as exc:
                # Persist final state while Playwright is still available.
                if isinstance(exc, KeyboardInterrupt):
                    errors.append({"error": "Người dùng dừng; chạy lại cùng --output và --resume."})
                else:
                    errors.append({"error": str(exc), "type": type(exc).__name__})
                print("DỪNG:", errors[-1]["error"], flush=True)
                if isinstance(reader, HttpReader) and reader.last_html:
                    (out / "last_page.html").write_text(reader.last_html, encoding="utf-8")
                elif reader and page and not page.is_closed():
                    try:
                        (out / "last_page.html").write_text(page.content(), encoding="utf-8")
                    except Exception:
                        pass
            finally:
                # Include a partially saved collection if access stopped mid-pagination.
                known_urls = {r["url"] for r in records}
                for url in attempted:
                    if url not in known_urls and collection_file(out, url).exists():
                        records.append(load(collection_file(out, url)))
                status = summarize(out, records, queue, attempted, errors, args.check)
                if browser:
                    browser.close()
    except ImportError:
        errors.append({"error": "Chưa cài Playwright: python -m pip install -r requirements.txt"})
        status = summarize(out, records, queue, attempted, errors, args.check)
    print(json.dumps(status, ensure_ascii=False, indent=2), flush=True)
    print("Kết quả:", out, flush=True)
    return 0 if status["status"] in ("check_passed", "finished_discovered_scope") else 2


if __name__ == "__main__":
    sys.exit(main())
