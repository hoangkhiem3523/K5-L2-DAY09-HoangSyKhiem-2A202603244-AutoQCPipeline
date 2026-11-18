# Báo cáo Day 09 — Hoàng Sỹ Khiêm, 2A202603244

## 1. Kết luận trước

Pipeline kết luận **Hold** (mã thoát `10`, `submission/reports/08_summary.json`). Từ **224 ảnh** đầu vào (`data/raw`), cổng cửa vào loại **21 ảnh** (còn **203/224 ảnh** xuất bản nháp vào `submission/export/clean_v1/` để thử nghiệm train). Toàn bộ lỗi bắt buộc (`ERROR`) đã giảm về **0/203**, nhưng do hàng đợi người duyệt có **125 ảnh** trong khi ngân sách cố định là **80 ảnh**, vẫn còn **38/203 ảnh (18.7%)** mang cảnh báo `WARN` chưa được người kiểm tra — vượt ngưỡng chặn Hold `10.0%` nên chưa đủ điều kiện phát hành (`Release`).

## 2. Lỗi và phân việc

Thống kê từ `submission/reports/02_error_list_v1.txt` và `01_intake.csv` (mẫu số cửa vào: **224 ảnh**; mẫu số QC vòng 1 trên ảnh hợp lệ: **203 ảnh**, tổng cộng **36 dòng `ERROR`** + **149 dòng `WARN`**):

| Mã lỗi | Mức độ | Số ảnh / dòng | Ai sửa (máy / người) | Vì sao |
|---|---|---:|---|---|
| `CORRUPT_IMAGE` | ERROR | 2/224 ảnh (`img_0010`, `img_0136`) | Máy (intake/autofix) | Không giải mã được ảnh (`UnidentifiedImageError`, ảnh cắt cụt `OSError`); loại an toàn ở cửa vào |
| `BAD_SIZE` | ERROR | 3/224 ảnh (`img_0107`, `0113`, `0122`) | Máy (intake/autofix) | Cạnh ngắn 180–226 px < ngưỡng dự án 250 px |
| `LEAK_TEST` | ERROR | 5/224 ảnh (`img_0049`, `0101`, `0167`, `0174`, `0221`) | Máy (intake/autofix) | Trùng trực tiếp ảnh trong `data/test` (`test_033`, `039`, `044`, `085`, `009`); bắt buộc loại để tránh rò rỉ đánh giá |
| `DUP_IMAGE_EXACT` | ERROR | 8/224 ảnh | Máy (intake/autofix) | Trùng từng byte MD5 với ảnh đứng trước |
| `DUP_IMAGE_NEAR` | ERROR | 3/224 ảnh (`img_0076`, `0143`, `0223`) | Máy (intake/autofix) | Trùng gần đúng với `phash_dist <= 8` (khoảng cách 0, 0, 6) |
| `BAD_CLASS_NAME` | ERROR | 2 dòng (`data.yaml`: `'Person'`, `'Bus'`) | Máy (`autofix: rename_classes`) | Sai chữ hoa/thường so với `cfg["classes"]`, chuẩn hoá lại hoàn toàn an toàn |
| `BAD_FORMAT` | ERROR | 3 dòng (`img_0014`, `0022`, `0179`) | Máy (`autofix: drop_line`) | Chứa `nan` hoặc thiếu cột (4/5 cột), không có toạ độ hợp lệ để cứu |
| `BAD_CLASS_ID` | ERROR | 6 dòng (ID `93`, `-1`, `7`, `4`) | Máy (`autofix: drop_line`) | ID ngoài `0..3`, không thể đoán lớp đúng bằng quy tắc cú pháp |
| `BOX_ZERO` | ERROR | 4 dòng (`img_0050`, `0066`, `0092`, `0185`) | Máy (`autofix: drop_line`) | `w = 0` hoặc `h = 0`, box rỗng vô nghĩa |
| `DUP_BOX` | ERROR | 7 dòng | Máy (`autofix: drop_line`) | Lặp cùng lớp IoU > 0.9 với dòng trước trong cùng ảnh |
| `BOX_OUT_OF_IMAGE` | ERROR | 8 dòng | Máy (`autofix: clip_box`) | Box tràn mép 0.023–0.060; cắt về `[0, 1]` giữ nguyên lớp an toàn (ghi đầy đủ trước → sau vào `03_fixes.csv`) |
| `MISSING_LABEL_FILE` | ERROR | 6/203 ảnh (`img_0031`, `0053`, `0126`, `0135`, `0170`, `0219`) | **Người** (`autofix` chỉ ghi `needs_label`) | Máy không được bịa nhãn hay tạo file rỗng (file rỗng nghĩa là "ảnh nền", khác "chưa gán") |
| `POSSIBLE_MISSING` | WARN | 53 dòng | **Người** (hàng đợi) | Lỗi ngữ nghĩa dựa trên ý kiến thứ hai (`yolo26l`); model cũng có thể nhận nhầm nên chỉ cảnh báo |
| `POSSIBLE_LOOSE_BOX` | WARN | 28 dòng | **Người** (hàng đợi) | Box lỏng/lệch (IoU 0.30–0.49), cần mắt người xác nhận biên vật thật |
| `POSSIBLE_FALSE_POS` | WARN | 25 dòng | **Người** (hàng đợi) | Nhãn không khớp dự đoán model (có thể là box thừa hoặc vật khuất mà model bỏ sót) |
| `POSSIBLE_WRONG_CLASS` | WARN | 18 dòng | **Người** (hàng đợi) | Nghi nhầm giữa các lớp hợp lệ (`car`/`person`/`truck`/`bus`), bắt buộc người quyết định |
| `EMPTY_LABEL`, `BOX_TINY`, `BOX_HUGE`, `CLASS_RARE` | WARN | 12 / 6 / 3 / 4 dòng | **Người** (hàng đợi / theo dõi) | Cảnh báo thống kê và biên kích thước, không tự xoá |

**Giải thích hàng đợi (`05_review_queue.csv`) và độ phủ ngân sách 80 ảnh:**
- Hàng đợi chấm điểm ưu tiên theo trọng số trong `configs/pipeline.yaml`: ảnh có `NEEDS_LABEL` (+10 điểm) và ảnh chồng nhiều lỗi nặng (`POSSIBLE_WRONG_CLASS` +3, `POSSIBLE_MISSING` +2, `FIXED_DROP_LINE` +2) được đẩy lên đầu. Vì vậy `img_0020` đứng số 1 (11.524 điểm: vừa bị xoá dòng ID `93`, vừa có `POSSIBLE_MISSING` và `POSSIBLE_WRONG_CLASS`), tiếp theo là đủ **6/6 ảnh `NEEDS_LABEL`** (10.0 điểm) để đảm bảo dứt điểm toàn bộ lỗi `ERROR` trước.
- Với ngân sách **80/125 ảnh** trong hàng đợi (`06_review_log.csv`), người duyệt đã xử lý **6/6 ảnh thiếu file nhãn** và **74/103 ảnh có cảnh báo ngữ nghĩa**, phủ được **94/123 cảnh báo ngữ nghĩa (76.4%)**. Cụ thể trên `04_error_list_v2.csv → 07_error_list_v3.csv`: `POSSIBLE_WRONG_CLASS` giảm từ `18 → 3` (xử lý 83.3%) và `POSSIBLE_MISSING` giảm từ `53 → 13` (xử lý 75.5%).

## 3. Calibration (2 ngưỡng)

Số liệu từ `submission/calibration/calibration_report.md` trên **39 ảnh `data/calib/`** (toàn bộ 7 check cú pháp và `DUP_IMAGE_EXACT` đạt `1.00 / 1.00 / 1.00`):

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau trên `calib`) | Lý do (đánh đổi) |
|---|---:|---:|---|---|
| `duplicates.phash_dist` | `2` | **`8`** | `DUP_IMAGE_NEAR`: `1.00 / 0.50` → **`1.00 / 0.67`** (`EXACT` giữ `1.00 / 1.00`) | Lỗi cửa vào tự động **xoá vĩnh viễn ảnh** nên ưu tiên **Precision = 1.00** (không xoá nhầm ảnh khác nhau). Mức `2` quá chặt (sót 50%); vùng `4–14` ổn định ở `1.00 / 0.67`; mức `16` tăng Recall lên `0.83` nhưng sát ngưỡng sập (`20` khiến `EXACT` tụt xuống `0.33`). Chọn `8` ở giữa vùng an toàn. |
| `second_opinion.conf` | `0.25` | **`0.6`** | `WRONG_CLASS`: `0.56 / 0.83` → **`0.62 / 0.83`**; `MISSING`: `0.50 / 1.00` → **`0.57 / 1.00`** | Tại `0.25` sinh nhiều báo động giả làm phình hàng đợi; tăng lên `0.6` giữ nguyên **Recall = 1.00** cho `MISSING` và `0.83` cho `WRONG_CLASS` trong khi tăng Precision (F1 `MISSING` đạt đỉnh `0.73`). Không nâng lên `0.7–0.8` vì `MISSING` bắt đầu rớt Recall (`0.88 → 0.75`) gây bỏ sót vật thật để ép Release giả. |

**Điểm calibration có thể đánh lừa (kèm bằng chứng thực tế):**
1. **Hiệu ứng mẫu nhỏ (39 ảnh) & bẫy F1 cao nhất trên `phash_dist = 16`:** Bộ `calib` chỉ có 6 ảnh gần trùng (mỗi ảnh đổi là Recall nhảy 16.7%), và cảnh ít trùng lặp hơn lô `raw` 224 ảnh. Nếu máy móc chọn `phash_dist = 16` vì F1 = 0.91 trên `calib`, rủi ro xoá nhầm ảnh khác nhau trên `raw` rất cao (thực tế ở `20` đã sập). Với `phash_dist = 8`, kiểm tra `01_intake.csv` cho thấy chỉ loại đúng **3 ảnh `DUP_IMAGE_NEAR`** (`img_0076` dist 0, `img_0143` dist 0, `img_0223` dist 6) — hoàn toàn hợp lý, không xoá oan ảnh tốt.
2. **Đánh đổi ẩn trên `LOOSE_BOX` và sự "bất biến" của `FALSE_POS`:** Khi nâng `conf` từ `0.25 → 0.6`, F1 của `MISSING` và `WRONG_CLASS` đẹp lên nhưng Recall của `POSSIBLE_LOOSE_BOX` lại tụt từ `0.40 → 0.20` (chỉ bắt 1/5 ca trong `calib`); đồng thời `POSSIBLE_FALSE_POS` đứng yên ở Precision `0.36` vì dùng ngưỡng `fp_conf = 0.1` cố định. Hơn nữa, `calib` không có ca `LEAK_TEST` và lỗi `WRONG_CLASS` trên `calib` chủ yếu là `person/car`, khác phân bố `raw` (lẫn nhiều `car/truck/bus`).

## 4. Cửa chặn và điều pipeline KHÔNG bắt được

**(a) Chứng minh cửa chặn hoạt động đúng (`--budget 0`):**
Chạy lệnh cô lập `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`:
- Sau `autofix`, vẫn còn nguyên **6 lỗi bắt buộc `MISSING_LABEL_FILE`** (`img_0031`, `0053`, `0126`, `0135`, `0170`, `0219`) vì không có người duyệt (`budget = 0`) và máy bị cấm tự tạo file nhãn.
- Cửa chặn `gate` lập tức kết luận **`REWORK`**, trả đúng **mã thoát `20`** (`NO_BUDGET_EXIT=20`), và **chặn cứng không xuất dataset** (`work/exp_nb/clean_v1` không được tạo — `Test-Path` trả `False`).

**(b) Ba điểm mù mà pipeline KHÔNG bắt được (kèm bằng chứng từ soi ảnh trực tiếp Bước 1 trên CVAT & báo cáo):**
1. **Ảnh trùng bị biến dạng mạnh (cắt sâu / xoay / thay đổi khung hình lớn):** Trên `calib`, ngay cả ở `phash_dist = 8`, 2/6 ảnh gần trùng vẫn lọt (`Recall = 0.67`) vì cấu trúc tần số ảnh bị biến đổi vượt khoảng cách Hamming 8.
2. **Vật nhỏ, bị khuất hoặc nằm ở biên tin cậy mà cả model lớn (`yolo26l`) cũng bỏ sót hoặc lệch nhẹ:** Khi tự soi 12 ảnh đầu trên CVAT ở Bước 1, mắt người phát hiện thêm nhiều box thiếu hoặc lệch tinh vi như `+2 car` và nắn nhẹ `car (IoU = 0.91)` ở `img_0007.jpg` (IoU > 0.5 nên `POSSIBLE_LOOSE_BOX` hoàn toàn im lặng), và `+1 person` bị khuất ở `img_0015.jpg`. Ngược lại, ở `img_0015.jpg` (lệch nặng `IoU = 0.49`), `img_0001.jpg` (sót `person`), `img_0004.jpg` (nhãn rỗng nhưng có `car`), `img_0020.jpg` (ID `93` + thừa box) và `img_0030.jpg` (thừa `person`), máy và mắt người đồng thuận tốt.
3. **Nhầm lớp ngữ nghĩa khi model lớn cùng nhận nhầm hoặc độ tin cậy dưới `0.6`:** Với các xe bán tải / xe tải nhẹ (`car ↔ truck ↔ bus`), nếu `yolo26l` dự đoán với `conf < 0.6` hoặc cùng gán sai giống nhãn thô, `second_opinion` sẽ không phát cảnh báo. Ngoài ra, **38 ảnh cảnh báo nằm ngoài top 80** vẫn chưa được người duyệt trong vòng này.

## 5. Train: `raw` vs `clean`

Thí nghiệm chạy cục bộ công bằng trên GPU **NVIDIA GeForce RTX 3050 Laptop (4GB)** bằng `scripts/train_compare.py` (`yolo26n.pt`, `epochs = 20`, `batch = 8`, `imgsz = 640`, cùng `gold_val` 40 ảnh và `test` 100 ảnh, 2 seed `0, 1`). Bảng tổng hợp sinh tự động từ `submission/results/comparison.md` (biểu đồ: `submission/results/comparison.png`):

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---:|---:|---|---|---|---|
| raw | 224 | 2 | 0.457 ± 0.005 | 0.315 ± 0.004 | 0.573 ± 0.092 | 0.446 ± 0.025 |
| clean | 203 | 2 | 0.456 ± 0.002 | 0.314 ± 0.005 | 0.513 ± 0.063 | 0.482 ± 0.043 |

Chênh `mAP50 (clean − raw)` = **`-0.001`**; chênh `mAP50-95` = **`-0.001`**. Chi tiết `AP50` trung bình 2 seed theo từng lớp (`submission/results/*_seed*.json`):
- `person`: `0.707` (`raw`) → **`0.742` (`clean`, +0.035)**
- `bus`: `0.386` (`raw`) → **`0.459` (`clean`, +0.073)**
- `car`: `0.514` (`raw`) → `0.483` (`clean`, -0.031)
- `truck`: `0.221` (`raw`) → `0.139` (`clean`, -0.082)

**Phân tích trung thực & giả thuyết:**
- **Kết luận trung thực:** Chênh lệch `mAP50 = -0.001` và `mAP50-95 = -0.001` **nhỏ hơn độ lệch chuẩn giữa các seed (`±0.005`)**, vì vậy **chưa thể kết luận `clean` tốt hơn `raw` về mAP tổng** trong thiết lập 20 epoch / 2 seed hiện tại. Tuy nhiên, `clean` tăng rõ ở **Recall tổng (`0.446 → 0.482`, +3.6%)**, `AP50 person (+3.5%)` và `AP50 bus (+7.3%)`, đồng thời giảm phương sai `mAP50` giữa các seed (`±0.005 → ±0.002`).
- **Ba giả thuyết giải thích vì sao `raw` không thấp hơn `clean` trên mAP tổng và cách kiểm chứng:**
  1. **Rò rỉ 5 ảnh tập `test` trong `raw` (`LEAK_TEST`):** `raw` giữ nguyên 5/100 ảnh trùng tập `test` (`test_009`, `033`, `039`, `044`, `085`), làm điểm đo của `raw` bị **thổi phồng ảo** do học thuộc mẫu test. *Cách kiểm:* Đánh giá lại cả 2 model trên 95 ảnh test đã bỏ 5 ảnh bị rò rỉ.
  2. **`clean` mới ở mức `Hold` (chưa duyệt hết 38 ảnh cảnh báo) và lớp `truck` quá ít mẫu:** Theo `class_stats.csv`, trong 203 ảnh `clean_v1` chỉ có **41 box `truck`** và **32 box `bus`** (so với 575 `person`, 101 `car`). Trong `07_error_list_v3.txt` vẫn còn 3 ca `POSSIBLE_WRONG_CLASS` đều nghi nhầm `truck ↔ car` (`img_0078`, `0083`, `0220`) và 1 ca sót `truck` (`img_0160`) chưa được người duyệt — khiến `AP50` của `truck` sụt mạnh (`-0.082`) và kéo tụt trung bình 4 lớp. *Cách kiểm:* Duyệt nốt 38 ảnh còn lại (đặc biệt các ảnh chứa `truck`), rồi chạy lại train so sánh ở 40 epoch với 3 seed.
  3. **Khác biệt cỡ tập train (224 vs 203 ảnh) và 20 epoch chưa hội tụ hoàn toàn trên lớp hiếm:** Tập `test` chỉ 100 ảnh nên biến động từng lớp nhỏ rất cao; cần tăng lên ≥ 3 seed và 40 epoch để tách tín hiệu khỏi nhiễu.

## 6. Quyết định và ghi chú AI

**(a) Quyết định cuối cùng:** **HOLD** (khớp `08_summary.json`: `0` lỗi bắt buộc, `38/203 = 18.7%` ảnh còn cảnh báo chưa duyệt `>= 10.0%`).  
**Điều kiện để chuyển sang `Release`:** Duyệt thêm ít nhất **18–38 ảnh** còn lại trong hàng đợi `05_review_queue.csv` (ưu tiên 3 ảnh `POSSIBLE_WRONG_CLASS` của `truck` và 13 ảnh `POSSIBLE_MISSING`) để kéo tỉ lệ ảnh cảnh báo chưa duyệt xuống dưới `< 10.0%` (`< 20/203` ảnh), sau đó chạy lại `python -m pipeline.run` xác nhận mã thoát `0` rồi mới phát hành bản chính thức.

**(b) Ghi chú sử dụng AI:**
- **Prompt chính:** Sử dụng ChatGPT/AI để gợi ý cấu trúc hàm theo đúng đặc tả đầu vào/đầu ra 4 ý cho các module kiểm tra cú pháp, logic gom sửa theo dòng của `autofix`, quy trình ưu tiên ghép box IoU của `second_opinion`, và định dạng bảng Markdown cho báo cáo.
- **Cách kiểm tra code AI:** Chạy toàn bộ **79/79 unit test & e2e test (`pytest -q`)**, kiểm tra thêm các ca biên (dòng trống giữa file, một dòng dính đồng thời 2 lỗi, ảnh vừa bị xoá vẫn còn issue), đối chiếu trực tiếp bằng mắt trên CVAT local và chạy thí nghiệm `--budget 0` để xác minh cửa chặn.
- **Một lần AI sai đã phát hiện & sửa:** Ở bản nháp đầu cho `autofix`, AI gợi ý xoá từng dòng theo chỉ số tuần tự khi duyệt danh sách `issues` (làm lệch số dòng gốc khi một file có nhiều dòng lỗi hoặc có dòng trống ở giữa) và dễ ghi cả `clip_box` lẫn `drop_line` cho cùng 1 dòng; đã sửa sang gom `drop_set` và `clip_set - drop_set` theo từng ảnh rồi ghi lại file đúng một lần.

**(c) Thưởng +2 (tùy chọn) — Lọc box nhỏ trên CVAT (`docs/CVAT_FILTER.md`):**
- Đã tạo Project `K5-L23-DAY09-AutoQC-Pipeline` bằng [cvat/labels.json](../cvat/labels.json) và nạp Task `Day09_Bonus_CVAT_Filter` gồm **25 ảnh** (top 20 ảnh đầu `05_review_queue.csv` + các ảnh chứa `BOX_TINY` từ `work/run/ds/`, tổng **164 box**).
- Áp dụng bộ lọc `width < 20` trong CVAT khớp **24 box trên 9 ảnh**: `img_0020` (3 box), `img_0026` (6 box), `img_0030` (3 box), `img_0051` (3 box), `img_0053` (1 box), `img_0069` (2 box), `img_0135` (2 box), `img_0161` (3 box), `img_0183` (1 box).
- **Đối chiếu với `BOX_TINY` của pipeline (`< 12 px`):** Toàn bộ **7 box `BOX_TINY`** trong `07_error_list_v3.txt` trên 5 ảnh (`img_0026`: 11.4 px, `img_0051`: 8.9 px, `img_0069`: 11.2 px, `img_0161`: 10.3 / 11.4 / 11.9 px, `img_0183`: 11.8 px) đều nằm gọn trong tập 24 box lọc được của CVAT. 17 box còn lại nằm trong khoảng `12–20 px` đa phần là `person` đứng thẳng ở xa (cao 30–75 px nhưng hẹp ngang 12–19.9 px), cho thấy ngưỡng `12 px` của pipeline ít báo động giả hơn ngưỡng `20 px` của slide trên lớp người đi bộ.
- **Về thuộc tính `can_review`:** Người gán nhãn tick `can_review = true` khi gặp ca mơ hồ về quy tắc hoặc khó nhìn (vật bị che khuất, ranh giới `car/truck/bus` không rõ) để yêu cầu reviewer kiểm tra lại; trong pipeline tự động, vai trò tương đương chính là các cảnh báo `WARN` từ `second_opinion` được quy đổi thành điểm ưu tiên trong `05_review_queue.csv`.
