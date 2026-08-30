# BOT LỌC COIN SHORT — Tiêu chí F1–F6 (Binance USDT-M Futures)

Bot quét **toàn bộ coin PERPETUAL USDT trên Binance Futures mỗi 5 phút**, chấm điểm theo
bộ tiêu chí **F1–F6** trong tài liệu `Cach_thuc_Bot_SHORT_F1_F6_Entry_SL_TP-3_1.pdf`
và in ra **tất cả coin đạt từ 50/100 điểm trở lên**, kèm Entry / SL / TP1–TP3.

Chỉ dùng **public API** của Binance → **không cần API key**, bot chỉ đọc dữ liệu, không đặt lệnh.

---

## 1. Cài đặt (kể cả khi chuyển sang máy mới)

### Cách nhanh nhất — 1 click

Copy cả thư mục project sang máy mới, rồi **double-click `setup.bat`**.
Script sẽ tự: kiểm tra Python → nâng cấp pip → cài thư viện → kiểm tra kết nối
Binance + Telegram → in ra các bước tiếp theo.

### Hoặc chạy bằng lệnh

```powershell
cd "d:\Bot_lọc"
pip install -r requirements.txt     # cài thư viện
python check_env.py                 # kiểm tra mọi thứ đã OK chưa
```

### Yêu cầu

- **Python 3.10+** — tải tại [python.org/downloads](https://www.python.org/downloads/)
  > ⚠️ Khi cài, **nhớ tick ô "Add Python to PATH"**, nếu không lệnh `python` sẽ không chạy được.
- **Chỉ 2 thư viện ngoài** (mọi thứ còn lại là thư viện chuẩn của Python):

| Thư viện | Vai trò | Bắt buộc? |
|---|---|---|
| `requests` | Gọi REST API Binance Futures + Telegram Bot API | ✅ Có |
| `pypdf` | Đọc file PDF tiêu chí (chỉ dùng cho `extract_pdf.py`) | ❌ Không — bot vẫn chạy nếu thiếu |

### Chuyển sang máy mới — checklist

1. Copy **toàn bộ thư mục** (gồm `config.py` — chứa token và ngưỡng của bạn).
2. Chạy `setup.bat` (hoặc `pip install -r requirements.txt`).
3. Chạy `python check_env.py` → phải thấy **"SAN SANG!"**.
4. Chạy `python test_scoring.py` và `python test_commands.py` → phải PASS hết.
5. Chạy bot: `run_bot.bat`

> 💡 File `telegram_subscribers.json` lưu danh sách người nhận cảnh báo.
> Copy sang cùng thì không cần `/start` lại; nếu không copy, chỉ cần gửi
> `/start` cho bot một lần trên máy mới là xong.

> 🐍 **Dùng virtual environment** (tùy chọn, gọn gàng hơn):
> ```powershell
> python -m venv .venv
> .\.venv\Scripts\Activate.ps1
> pip install -r requirements.txt
> ```
> Lần sau chạy bot phải `Activate.ps1` trước.

## 2. Chạy bot

```powershell
python main.py                  # Chạy liên tục, quét mỗi 5 phút (mặc định)
python main.py --once           # Quét 1 lần rồi thoát
python main.py --min-score 60   # Đổi ngưỡng điểm cho console/CSV
python main.py --interval 180   # Đổi chu kỳ quét sang 3 phút
python main.py --symbol KGENUSDT --once   # Soi 1 coin cụ thể
python main.py -v               # Log chi tiết (debug)
python test_scoring.py          # 170 test kiểm chứng logic F1-F6
python test_commands.py         # 80 test kiểm chứng lệnh Telegram (chat riêng + nhóm)

# --- Telegram ---
python main.py --test-telegram  # Gửi tin nhắn mẫu, kiểm tra token/chat_id
python main.py --once --preview # In tin nhắn của coin thật, KHÔNG gửi
python main.py --min-pass 2     # Đẩy Telegram khi >= 2 tiêu chí PASS (mặc định)
python main.py --quality        # Chống spam: bỏ coin chỉ PASS F5+F6
python main.py --no-telegram    # Tắt Telegram lần chạy này
python main.py --ignore-cooldown # Bỏ qua cooldown 30 phút
```

**Bảng CLI đầy đủ**

| Flag | Ý nghĩa |
|---|---|
| `--once` | Quét 1 lần rồi thoát |
| `--interval N` | Chu kỳ quét (giây), mặc định 300 |
| `--min-score N` | Ngưỡng điểm cho console/CSV, mặc định 50 |
| `--min-pass N` | Số tiêu chí PASS tối thiểu để đẩy Telegram, mặc định 2 |
| `--tele-min-score N` | Điểm sàn riêng cho Telegram |
| `--quality` | Chỉ đẩy coin PASS ≥1 trong F1/F2/F3/F4 |
| `--symbol XXXUSDT` | Soi 1 coin + in tin nhắn của nó |
| `--preview` | In tin nhắn thay vì gửi |
| `--test-telegram` | Gửi tin nhắn mẫu để test kết nối |
| `--no-telegram` / `--no-csv` | Tắt Telegram / tắt ghi CSV |
| `--ignore-cooldown` | Gửi lại cả coin vừa gửi gần đây |
| `-v` | Log chi tiết |

Hoặc double-click **`run_bot.bat`**.

## 3. Thang điểm 100

Trọng số phân bổ theo cột **"Mức độ"** trong PDF:

| Bộ lọc | Dữ liệu | Ngưỡng PASS (PDF) | Điểm | Mức độ |
|---|---|---|---|---|
| **F1** | RSI 15m / 4H / 1D | ≥ 90 / ≥ 80 / ≥ 65 | **30** (12+10+8) | Rất quan trọng |
| **F4** | Open Interest (1h) | ≥ +8% | **20** | Rất quan trọng |
| **F2** | Long/Short account ratio | Long ≥ 65% | **15** | Quan trọng |
| **F3** | Spike nến 15m | ≥ 7% | **15** | Quan trọng |
| **F6** | Funding rate | ≥ −0.15% | **12** | Hard filter |
| **F5** | Upper wick ratio | ≥ 0.30 | **8** | Xác nhận |
| | | | **= 100** | |

**Chấm điểm từng phần (partial credit):** mỗi tiêu chí có một "ramp" tuyến tính
(xem `config.RAMPS`) — dưới ngưỡng thấp = 0 điểm, đạt ngưỡng PASS = full điểm.
Nhờ vậy coin *gần* đạt chuẩn vẫn có điểm và có thể vượt mốc 50/100 để bạn theo dõi sớm.

Ví dụ F1 RSI 15m: `RSI ≤ 70 → 0 điểm`, `RSI = 80 → 6 điểm`, `RSI ≥ 90 → 12 điểm`.

## 4. Cách đọc kết quả

```
  # SYMBOL          SCORE GR ACT    RSI15m  RSI4H  RSI1D  LONG%  SPIKE   OI-1h  WICK    FUND%  TRAP  F1-F6
  1 4USDT            80.3 A  SHORT    95.1   80.5   71.5   60.3   1.89   31.51  0.44   0.0583   6.5  +--+++
```

- **SCORE** — điểm /100.
- **GR** — hạng: `A+` (F1–F6 full PASS & ≥85đ) › `A` › `B+` › `B` › `C+` › `C`.
- **ACT** —
  - `SHORT`: **F1 và F6 đều PASS** → đúng điều kiện bắt buộc của PDF.
  - `WAIT`: F1 hoặc F6 FAIL → PDF khuyến nghị **không vào lệnh**, chỉ theo dõi.
- **F1-F6** — chuỗi 6 ký tự theo thứ tự F1→F6: `+` = PASS, `-` = FAIL.
  Ví dụ `+--+++` = F1 PASS, F2 FAIL, F3 FAIL, F4 PASS, F5 PASS, F6 PASS.
- **TRAP** — Trap Risk 0–10 (rủi ro long squeeze / bẫy giá khi short); càng cao càng nên thận trọng.

Entry / SL / TP theo công thức mục 4–6 của PDF, đã làm tròn theo **tick size** từng coin:

```
ENTRY = giá thị trường lúc tín hiệu   |   SL = Entry × 1.013  (+1.3%)
TP1 = Entry × 0.965 (−3.5%)  |  TP2 = Entry × 0.902 (−9.8%)  |  TP3 = Entry × 0.850 (−15%)
```

## 5. Cấu trúc file

| File | Vai trò |
|---|---|
| `config.py` | **Toàn bộ ngưỡng & trọng số** — sửa ở đây, không cần sửa code logic |
| `binance_client.py` | Gọi public REST API Binance Futures (có retry, xử lý 429) |
| `indicators.py` | RSI Wilder-14, spike 15m, upper wick ratio, Entry/SL/TP, round tick |
| `scoring.py` | Áp dụng F1–F6, chấm điểm /100, xếp hạng, Trap Risk |
| `scanner.py` | Prefilter toàn sàn + fetch song song + tổng hợp kết quả |
| `reporter.py` | In bảng console, ghi CSV, tóm tắt Telegram |
| `telegram_notifier.py` | Dựng tin nhắn (format ảnh + `/search`), gửi Telegram, cooldown, quản lý subscriber |
| `telegram_bot.py` | **Thread lắng nghe lệnh** `/start` `/search` `/top` `/status` `/help` `/stop` |
| `main.py` | Entry point + vòng lặp 5 phút + CLI + khởi động thread lệnh |
| `test_scoring.py` | **170 test** — logic F1–F6, chấm điểm, ưu tiên, format tin nhắn, rate limiter |
| `test_commands.py` | **80 test** — lệnh Telegram ở chat riêng + trong nhóm (giả lập, không gửi thật) |
| `add_subscriber.py` | Thêm thủ công `chat_id` vào danh sách nhận cảnh báo |
| `setup.bat` | **Cài đặt 1 click** trên máy mới (Python → pip → thư viện → kiểm tra) |
| `check_env.py` | Chẩn đoán môi trường: Python, thư viện, config, kết nối Binance/Telegram |
| `run_bot.bat` | Chạy bot, tự khởi động lại nếu crash |
| `requirements.txt` | Danh sách thư viện (`requests`, `pypdf`) |
| `extract_pdf.py` | Trích text từ PDF tiêu chí |
| `signals/signals_YYYYMMDD.csv` | Log tín hiệu để backtest |
| `telegram_sent.json` | Thời điểm gửi gần nhất mỗi coin (cooldown) |
| `telegram_subscribers.json` | Danh sách `chat_id` đã `/start` |
| `bot.log` | Log hoạt động |

## 6. Tinh chỉnh trong `config.py`

```python
MIN_SCORE = 50.0                    # Ngưỡng điểm báo tín hiệu
SCAN_INTERVAL_SECONDS = 5 * 60      # Chu kỳ quét
MIN_QUOTE_VOLUME_24H = 5_000_000    # Bỏ coin thanh khoản thấp
MIN_PRICE_CHANGE_24H = 2.0          # Chỉ xét coin tăng ≥ 2% trong 24h
REQUIRE_MANDATORY_PASS = False       # True = chỉ báo coin PASS cả F1 & F6
WEIGHTS / RAMPS                      # Trọng số & dải chấm điểm từng phần
```

**Muốn bot chỉ báo setup đủ chuẩn vào lệnh** (theo đúng khuyến nghị PDF):
đặt `REQUIRE_MANDATORY_PASS = True` → chỉ hiện coin PASS cả F1 và F6.

**Muốn quét rộng hơn** (kể cả coin không tăng): giảm `MIN_PRICE_CHANGE_24H` về `0`
và tăng `MAX_SYMBOLS_PER_SCAN`.

## 7. Thông báo Telegram — push mọi coin ≥ 2 tiêu chí PASS

### 7.1. Cấu hình — chỉ 3 bước

**Bước 1.** Điền token vào `config.py` (lấy từ [@BotFather](https://t.me/BotFather)):
```python
TELEGRAM_BOT_TOKEN = "123456:ABC..."
TELEGRAM_HEADER_NAME = "MMisMyEx"      # tên hiển thị đầu tin nhắn
```

> 🔒 **An toàn hơn** — đọc token từ biến môi trường, không để lộ trong code:
> ```python
> import os
> TELEGRAM_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
> ```
> ```powershell
> $env:TG_BOT_TOKEN = "123456:ABC..."   # đặt trước khi chạy bot
> ```

**Bước 2.** Chạy bot: `python main.py --quality`

**Bước 3.** Mở Telegram → tìm bot của bạn → bấm **Start** (hoặc gõ `/start`).

✅ **Không cần tìm `chat_id` thủ công.** Bot tự lưu `chat_id` vào
`telegram_subscribers.json`, và `TELEGRAM_AUTO_SUBSCRIBE = True` nên chỉ cần
gửi **bất kỳ lệnh nào** là đã được đăng ký. Gõ `/stop` để hủy.

Nhiều người/nhóm cùng nhận được: mỗi người chỉ cần `/start` một lần.
Muốn thêm thủ công khi đã biết `chat_id`:
```powershell
python add_subscriber.py 8048946417
```

Kiểm tra kết nối + xem trước format:
```powershell
python main.py --test-telegram      # gửi tin nhắn mẫu CHILLGUYUSDT
python main.py --once --preview     # in tin nhắn của coin thật, KHÔNG gửi
```

### 7.2. Điều kiện đẩy tin

Bot có **2 nhánh lọc độc lập** trong cùng 1 vòng quét:

| Nhánh | Điều kiện | Đích |
|---|---|---|
| Báo cáo | `score ≥ 50/100` | Console + CSV |
| **Telegram** | **≥ 4 tiêu chí PASS trong F1–F6** ⭐ | Tin nhắn Telegram |

```python
TELEGRAM_MIN_PASSED_FILTERS = 4         # số tiêu chí PASS tối thiểu
TELEGRAM_SORT_MODE = "PASS_THEN_SCORE"  # ưu tiên coin mạnh nhất lên đầu
TELEGRAM_SHOW_RANK = True               # đánh số #1 #2 #3 vào tin nhắn
TELEGRAM_ALSO_REQUIRE_MIN_SCORE = False # True = còn phải đạt MIN_SCORE
TELEGRAM_MIN_SCORE_FLOOR = 0.0          # điểm sàn riêng cho Telegram
TELEGRAM_REQUIRE_ANY_OF = ()            # vd ("F1","F2","F3","F4")
```

**Hiệu quả lọc thực tế** — quét toàn bộ **522 coin**, chỉ gửi **tối đa 4 tin**:

| Ngưỡng | Số coin/vòng (trên 522 coin) | Nhận xét |
|---|---|---|
| ≥2 PASS | ~150+ | Quá nhiều, F5+F6 rất dễ PASS |
| **≥4 PASS** ⭐ | **1–5** | Chỉ coin thực sự đáng chú ý |
| ≥5 PASS | 0–1 | Rất hiếm, gần chuẩn SHORT |

```python
TELEGRAM_MAX_MESSAGES_PER_SCAN = 4   # chỉ gửi TOP 4 coin mạnh nhất
```
Dù có 10 coin đạt ≥4/6, bot chỉ gửi **4 coin mạnh nhất** — xem đủ danh sách bằng `/top`.

### Ưu tiên coin mạnh nhất

Coin được sắp xếp trước khi đẩy — coin **mạnh nhất gửi trước**:

1. **Số tiêu chí PASS** giảm dần (6/6 → 5/6 → 4/6)
2. Cùng số PASS → **điểm cao** trước
3. Cùng điểm → **Trap Risk thấp** trước

Mỗi tin nhắn được đánh số `#1/3 manh nhat` để bạn biết ngay coin nào đáng xem trước.

Đổi cách sắp xếp:
```python
TELEGRAM_SORT_MODE = "PASS_THEN_SCORE"  # mặc định
TELEGRAM_SORT_MODE = "SCORE_THEN_PASS"  # điểm trước, PASS sau
TELEGRAM_SORT_MODE = "SCORE"            # chỉ theo điểm
```

Đổi nhanh bằng CLI:
```powershell
python main.py --min-pass 5            # siết lên 5 PASS
python main.py --min-pass 2 --quality  # nới lỏng nhưng bỏ coin chỉ PASS F5+F6
python main.py --tele-min-score 60     # thêm điểm sàn 60
```

### 7.3. Chống spam

```python
TELEGRAM_COOLDOWN_MINUTES = 30          # không gửi lại cùng coin trong 30 phút
TELEGRAM_MAX_MESSAGES_PER_SCAN = 15     # tối đa 15 tin/vòng quét
TELEGRAM_SEND_DELAY = 1.2               # nghỉ 1.2s giữa 2 tin (tránh 429)
```
Thời điểm gửi gần nhất lưu ở `telegram_sent.json` → cooldown vẫn hiệu lực sau khi restart bot.
Dùng `--ignore-cooldown` để bỏ qua khi test.

### 7.4. Định dạng tin nhắn (khớp bot gốc)

Tin nhắn thật bot vừa gửi (dữ liệu Binance live):

```
Bot_v1_byTuanAnh    #1/3 manh nhat
🔍 4USDT · RSI 15m 89.7 4h 87.0 1D 70.9  (RSI6/12/24)
💲 0.020065  24h: +68.44%  1h: +8.55%  Vol: 0.7x
L/S 55.5%  FR +0.118%  OI 12.6M

——————————————————

❌ C · WAIT

📍 Entry: 0.020065
🔴 SL:  0.020366  (-1.5%)
🎯 TP1: 0.019313  (+3.7%) 2.5R
🎯 TP2: 0.01856   (+7.5%) 5R
🎯 TP3: 0.017808  (+11.2%) 7.5R

Score: 8.6/10  |  Trap risk: 5.5/10  |  PASS 4/6

F1: PASS — RSI6(15m)=89.67, RSI12(4h)=87.0, RSI24(1D)=70.85; F2: FAIL — L/S long
ratio=55.5% < 65%...; F3: FAIL — No 15m spike >= 5% (cao nhat at 13:30 UTC chi 4.4%);
F4: PASS — OI increased by 5.5% over the last 3 periods (11.0M to 12.6M);
F5: PASS — Upper wick seen at 13:30 UTC (ratio 0.77);
F6: PASS — Funding rate is 0.118%, not negative

📌 Long/Short ratio chua nghieng Long du manh, failing F2, F3, hence setup is not
strong enough for a short. (4/6 PASS, Score 86/100)
```

**Cách đọc:**
- `#1/3 manh nhat` — coin mạnh nhất trong 3 coin đủ điều kiện vòng quét này
- **Icon** — 🔥 = PASS đủ 6/6 (`SHORT`) · ⚠️ = 5/6 (sát chuẩn) · ❌ = 4/6
- `Score: 8.6/10` — điểm trên thang 10 (giống bot gốc), tương đương 86/100
- **`%` là lãi/lỗ của vị thế SHORT**: SL âm (`-1.5%` = lỗ), TP dương (`+3.7%` = lãi)
- `2.5R` — TP đạt 2.5 lần mức rủi ro (R = khoảng cách tới SL)
- Entry/SL/TP hiện cho **mọi** coin đủ điều kiện (coin `WAIT` là mức tham khảo)

### 7.5. Công thức Entry/SL/TP — 2 preset

```python
LEVELS_PRESET = "SCREENSHOT"   # hoặc "PDF"
```

| | `SCREENSHOT` (mặc định) | `PDF` |
|---|---|---|
| SL | Entry × **1.015** (+1.5%) | Entry × 1.013 (+1.3%) |
| TP1 | −3.75% = **2.5R** | −3.5% |
| TP2 | −7.5% = **5R** | −9.8% |
| TP3 | −11.25% = **7.5R** | −15% |

Preset `SCREENSHOT` được **verify khớp 100%** với ảnh tín hiệu thật:
Entry `0.013297` → SL `0.0135`, TP `0.0128 / 0.0123 / 0.0118`.

Giá luôn được làm tròn theo **tick size** của từng coin trên Binance.

## 8. Lệnh tương tác trên Telegram

Bot chạy **2 thread song song** trong cùng 1 process:
- **Thread quét** — mỗi 5 phút đẩy coin ≥2 PASS cho mọi subscriber
- **Thread lệnh** — long-polling, trả lời lệnh của bạn ngay lập tức

| Lệnh | Chức năng |
|---|---|
| `/search <coin>` | ⭐ **Soi chi tiết 1 coin**: từng tiêu chí F1–F6 PASS/FAIL, điểm từng phần, tổng điểm /100, Entry/SL/TP |
| `/top` | Top coin nhiều tiêu chí PASS nhất từ vòng quét gần nhất |
| `/status` | Trạng thái bot + toàn bộ ngưỡng F1–F6 đang dùng |
| `/start` | Đăng ký nhận cảnh báo tự động |
| `/stop` | Hủy nhận cảnh báo |
| `/help` | Hướng dẫn |

**`/search` linh hoạt** — mọi cách gõ sau đều ra `BTCUSDT`:
```
/search btc      /search BTC-USDT      /search btcusdt
/s btc           btc                   /search btc/usdt
```
Gõ sai tên → bot **gợi ý** các symbol gần giống. Có thể gõ thẳng tên coin
(không cần `/search`). Trong group, `/search@ten_bot btc` cũng hoạt động.

### Ví dụ kết quả `/search chillguy`

```
🔍 CHILLGUYUSDT — CHI TIET F1-F6

💲 Gia 0.01464  |  24h +17.00%  |  1h -0.28%
📊 Vol 15m 0.6x  |  Vol 24h 12.0M  |  OI 2.6M
📈 RSI6(15m) 70.05  RSI12(4h) 78.30  RSI24(1D) 67.81
⚖️ L/S 68.5%  |  Funding +0.0050%

❌ KET QUA: 93.3/100  ·  Hang C  ·  WAIT
✅ PASS 5/6 tieu chi  |  🎯 Trap Risk 4.5/10

——————————————————

✅ F1 · RSI 15m/4H/1D  (Rat quan trong)
   ██████████  30.0/30 diem
   → RSI6(15m)=70.05, RSI12(4h)=78.3, RSI24(1D)=67.81

✅ F2 · Long/Short Ratio  (Quan trong)
   ██████████  15.0/15 diem
   → L/S long ratio=68.5%

✅ F3 · Spike nen 15m  (Quan trong)
   ██████████  15.0/15 diem
   → Spike with 15m candle at 10:30 UTC increased by 6.1%

❌ F4 · Open Interest  (Rat quan trong)
   ███████░░░  13.3/20 diem
   → OI did not increase by 5% over the last 3 periods (2.5M to 2.6M)

✅ F5 · Upper Wick  (Xac nhan)
   ██████████  8.0/8 diem
   → Upper wick seen at 10:45 UTC (ratio 0.42)

✅ F6 · Funding Rate  (Hard filter)
   ██████████  12.0/12 diem
   → Funding rate is 0.005%, not negative

——————————————————

📐 Muc gia tham khao (chua du tieu chi - chi de theo doi)
Entry 0.01464
SL 0.01483  (+1.3%)
TP1 0.01413 (-3.5%)  TP2 0.01321 (-9.8%)  TP3 0.01244 (-15%)

📌 OI did not increase sufficiently, failing F4, hence setup is not
strong enough for a short. (5/6 PASS, Score 93/100)
```

Thanh `██████████` = tỷ lệ điểm đạt được trên điểm tối đa của tiêu chí đó.
Tiêu chí **FAIL vẫn có điểm từng phần** nếu giá trị nằm trong dải ramp
(ví dụ F4 ở trên: OI +4% chưa đạt ngưỡng 5% nhưng vẫn được 13.3/20).

### Config liên quan

```python
TELEGRAM_ENABLE_COMMANDS = True   # bật/tắt thread lắng nghe lệnh
TELEGRAM_AUTO_SUBSCRIBE = True    # gửi lệnh nào cũng được đăng ký nhận tin
TELEGRAM_POLL_TIMEOUT = 30        # long polling getUpdates (giây)
TELEGRAM_SEARCH_TOP_LIMIT = 10    # số coin tối đa cho /top
TELEGRAM_SUBSCRIBERS_FILE = "telegram_subscribers.json"
```

---

## 8b. Dùng bot trong NHÓM 👥

Cả nhóm cùng nhận cảnh báo và **mọi thành viên đều dùng được lệnh bot**.

### Thêm bot vào nhóm — 3 bước

**Bước 1.** Cho phép bot vào nhóm (thường đã bật sẵn):
[@BotFather](https://t.me/BotFather) → `/mybots` → chọn bot →
**Bot Settings** → **Allow Groups?** → **Turn on**

**Bước 2.** Mở nhóm → **Add members** → tìm `@ten_bot_cua_ban` → Add

**Bước 3.** Xong! Bot tự gửi tin chào và **tự đăng ký nhóm** nhận cảnh báo.

> Kiểm tra bằng cách gõ `/status` trong nhóm — phải thấy
> *"Chat nay: DANG nhan canh bao (nhom)"*.

### ⚠️ Privacy Mode — điều quan trọng nhất cần biết

Mặc định Telegram bật **Privacy Mode** cho bot trong nhóm:
bot **chỉ nhìn thấy tin nhắn bắt đầu bằng `/`**, không đọc được chat riêng tư
của mọi người. Đây là mặc định **tốt** (bảo mật + không spam), và bot đã được
thiết kế để hoạt động đúng với chế độ này.

**Nếu bot không phản hồi trong nhóm**, làm một trong hai cách:

| Cách | Làm gì | Ưu / nhược |
|---|---|---|
| **A. Gõ kèm @tên_bot** (khuyến nghị) | `/search@ten_bot btc` | Giữ Privacy Mode → an toàn |
| **B. Tắt Privacy Mode** | @BotFather → `/mybots` → Bot Settings → **Group Privacy** → **Turn off**, rồi **kick bot ra và add lại** | Gõ `/search btc` gọn hơn, nhưng bot thấy mọi tin nhắn nhóm |

> 💡 Cách A luôn hoạt động, không cần cấu hình gì. Bot cũng tự nhắc điều này
> trong tin nhắn chào và `/help`.

### Bot cư xử thế nào trong nhóm?

| Hành vi | Chi tiết |
|---|---|
| **Reply trực tiếp** | Bot reply vào tin của người hỏi + tag tên họ → nhóm đông vẫn biết ai hỏi gì |
| **Không spam chat thường** | Trong nhóm, gõ `btc` (không có `/`) sẽ **bị bỏ qua**. Chỉ chat riêng mới coi text thường là tên coin |
| **Bỏ tin "⏳ Đang lấy..."** | Trong nhóm chỉ gửi 1 tin kết quả, đỡ nhiễu |
| **Phân biệt nhiều bot** | Nhóm có nhiều bot? `/search@bot_khac btc` sẽ được bot này bỏ qua |
| **`/stop` chỉ admin** | Tránh 1 người tắt cảnh báo của cả nhóm. Muốn tự tắt riêng → chat riêng với bot rồi `/stop` |
| **Chống spam lệnh** | Mỗi người phải chờ **3 giây** giữa 2 lệnh |
| **Bị kick khỏi nhóm** | Bot tự xoá nhóm khỏi danh sách nhận tin |

### Config cho nhóm

```python
TELEGRAM_AUTO_SUBSCRIBE_GROUP = True   # tự đăng ký nhóm khi bot được add
TELEGRAM_REPLY_IN_GROUP = True         # reply vào tin của người hỏi
TELEGRAM_MENTION_USER_IN_GROUP = True  # tag tên người hỏi
TELEGRAM_GROUP_ADMIN_ONLY_STOP = True  # chỉ admin được /stop
TELEGRAM_GROUP_SHOW_LOADING = False    # ẩn tin "Đang lấy dữ liệu..."
TELEGRAM_USER_COOLDOWN_SECONDS = 3     # giây chờ giữa 2 lệnh mỗi người
TELEGRAM_PLAIN_TEXT_PRIVATE_ONLY = True  # text thường chỉ tính ở chat riêng
```

### Dùng nhiều nhóm + nhiều người cùng lúc

Không giới hạn: mỗi nhóm/người chỉ cần add bot (hoặc `/start`) một lần.
Tất cả đều nhận chung cảnh báo mỗi 5 phút. Xem tổng số người/nhóm đang nhận:
```powershell
python -c "import telegram_notifier as t; print(t.SubscriberStore().all())"
```

## 9. Preset tiêu chí: `PDF` vs `SCREENSHOT`

Ảnh tín hiệu thật của bot gốc tiết lộ tham số khác PDF, nên có 2 preset trong `config.py`:

```python
FILTER_PRESET = "SCREENSHOT"   # hoặc "PDF"
```

| | `SCREENSHOT` (mặc định) | `PDF` |
|---|---|---|
| Chu kỳ RSI | **6 / 12 / 24** (như `RSI6(15m)` trong ảnh) | 14 / 14 / 14 |
| Ngưỡng F1 | 70 / 70 / 65 | 90 / 80 / 65 |
| F3 spike | ≥ 5% (ảnh PASS ở 6.1%) | ≥ 7% |
| F4 OI | ≥ 5% qua **3** chu kỳ (như ảnh) | ≥ 8% qua 4 chu kỳ |

Hai config liên quan:
```python
SHORT_REQUIRES = "ALL"    # ảnh: FAIL F4 vẫn là WAIT -> cần PASS cả 6 mới SHORT
                          # "MANDATORY" = chỉ cần F1+F6 (theo câu khuyến nghị PDF)
GRADE_MODE = "SIMPLE"     # ảnh: 5/6 PASS vẫn ghi "C" -> full PASS mới A+/A
                          # "DETAILED" = chia nhỏ A+/A/B+/B/C+/C theo điểm
```

## 10. Quét TOÀN BỘ 524 coin & Rate limit

```python
SCAN_ALL_SYMBOLS = True        # quét hết mọi coin PERPETUAL USDT
MAX_SYMBOLS_PER_SCAN = 600
```

Bot quét **toàn bộ 522 coin** mỗi vòng (= 524 trên sàn − `BTCDOMUSDT` là chỉ số,
− `USDCUSDT` là stablecoin). Coin meme tên tiếng Trung (`我踏马来了USDT`, `龙虾USDT`)
**vẫn được quét** vì chúng có thật và từng ra tín hiệu.

**Kết quả thực đo:**
```
Quet TOAN BO 522/522 coin PERPETUAL USDT (uoc tinh ~1617 weight, tran 2000/phut)
  ... 100/522 coin (7s, weight 377/2000)
  ... 300/522 coin (19s, weight 980/2000)
  ... 500/522 coin (31s, weight 1578/2000)
Cham diem xong 521/522 coin trong 32s (weight da dung 1617/2000)
```
→ **32 giây/vòng**, dùng 81% hạn mức, còn dư 19% an toàn.

### Tối ưu weight quan trọng nhất

| | Trước | Sau |
|---|---|---|
| `KLINES_LIMIT` | 120 → weight **4** | **100** → weight **1** |
| Weight/coin | 12 | **3** |
| 524 coin | ~6300 (vượt trần ❌) | **1617** ✅ |

Binance tính weight `/fapi/v1/klines` theo `limit`: **≤100 → 1**, 101–500 → 2 (thực đo 4).
Chỉ cần hạ từ 120 xuống 100 là **giảm 4 lần weight**, mà 100 nến vẫn thừa cho
RSI 6/12/24 và volume trung bình 20 nến.

### Rate limiter tự động

Class `WeightLimiter` (trong `binance_client.py`) đọc header `x-mbx-used-weight-1m`
từ mỗi response để biết weight **thật** Binance đang tính, và tự chặn khi sắp chạm trần:

```python
MAX_WEIGHT_PER_MINUTE = 2000   # trần thật của Binance là 2400
MAX_WORKERS = 12               # số luồng song song
```

Endpoint `/futures/data/*` (long/short ratio, OI history) nằm ở **pool rate-limit
riêng**, không tính vào 2400/phút → bot bỏ qua khi đếm.

Gặp HTTP 429/418 bot tự chờ theo `retry_after` rồi thử lại.

### Muốn quét nhanh hơn / ít coin hơn?

```python
SCAN_ALL_SYMBOLS = False       # bật lại chế độ lọc sơ bộ
MIN_QUOTE_VOLUME_24H = 5_000_000
MIN_PRICE_CHANGE_24H = 2.0     # chỉ coin tăng >= 2% trong 24h
MAX_SYMBOLS_PER_SCAN = 120
```
→ chỉ quét ~40 coin, xong trong ~5 giây.

## 11. Lưu ý quan trọng

- Bot **chỉ lọc và cảnh báo**, **không tự đặt lệnh**.
- Công thức Entry/SL/TP là **tái dựng** từ 2 tín hiệu mẫu (PDF đã ghi rõ), không phải mã nguồn gốc.
- PDF khuyến nghị: SL 1.3% quá sát với coin biến động mạnh → nên bổ sung ATR;
  chốt từng phần tại TP1/TP2/TP3, sau TP1 dời SL về hoà vốn.
- **Backtest tối thiểu vài trăm lệnh** (dùng file CSV trong `signals/`) trước khi tăng vốn/đòn bẩy.
- Chỉ báo `F5 Upper Wick` dùng nến 15m đang chạy → giá trị có thể thay đổi tới khi nến đóng.

## 12. Bảo mật 🔒

⚠️ **Bot token trong `config.py` là bí mật.** Ai có token đều điều khiển được bot của bạn.

- Đã có `.gitignore` loại trừ `bot.log`, `signals/`, `telegram_sent.json`,
  `telegram_subscribers.json`, `__pycache__/`.
- **Nhưng `config.py` vẫn được commit** (vì chứa toàn bộ ngưỡng tiêu chí).
  → **Đừng push repo này lên GitHub public khi token còn nằm trong `config.py`.**
- Cách xử lý đúng: chuyển token sang biến môi trường (xem mục 7.1), hoặc thêm
  `config.py` vào `.gitignore` và commit một bản `config.example.py` không có token.
- Nếu token đã bị lộ: vào [@BotFather](https://t.me/BotFather) → `/revoke` → tạo token mới.

## 13. Chạy 24/7

Bot là script Python thường, muốn chạy liên tục:

**Windows Task Scheduler** — tạo task chạy `run_bot.bat` khi khởi động máy,
tick *"Run whether user is logged on or not"* và *"Restart if the task fails"*.

**Hoặc** giữ cửa sổ PowerShell mở với vòng tự khởi động lại nếu bot crash:
```powershell
cd "d:\Bot_lọc"
while ($true) { python main.py --quality; Start-Sleep -Seconds 10 }
```

Bot đã tự chịu lỗi: HTTP 429/418 của Binance → chờ + retry; lỗi mạng trong
vòng quét → log rồi tiếp tục vòng sau; chat bị block (400/403) → tự bỏ khỏi
danh sách nhận tin. Nên bot không tự chết giữa đêm.
