"""
Cau hinh Bot loc coin SHORT theo tieu chi F1-F6.

Nguon tieu chi: Cach_thuc_Bot_SHORT_F1_F6_Entry_SL_TP-3_1.pdf
Toan bo nguong duoi day co the sua truc tiep tai day, khong can sua code logic.
"""

# ---------------------------------------------------------------------------
# 1. VONG LAP QUET
# ---------------------------------------------------------------------------
SCAN_INTERVAL_SECONDS = 5 * 60      # Quet lai moi 5 phut (theo yeu cau)
MIN_SCORE = 50.0                    # Chi bao coin co diem >= 50/100
TIMEZONE = "Asia/Ho_Chi_Minh"

# ---------------------------------------------------------------------------
# 2. PREFILTER (loc so bo bang 2 request batch cho ca san, tiet kiem rate limit)
# ---------------------------------------------------------------------------
# SCAN_ALL_SYMBOLS = True -> quet TOAN BO coin PERPETUAL USDT (524 coin),
# bo qua moi bo loc so bo ben duoi. Da tinh toan: 524 coin x 3 klines = 1572
# weight, cong batch ~51 -> 1623/2400 moi phut, van an toan.
SCAN_ALL_SYMBOLS = True

MIN_QUOTE_VOLUME_24H = 0.0          # USDT: 0 = khong loc theo thanh khoan
MIN_PRICE_CHANGE_24H = -100.0       # %: -100 = lay ca coin dang giam
MAX_SYMBOLS_PER_SCAN = 600          # Tran an toan (san hien co ~524 coin)
# Bo hop dong dac biet / index (khong phai coin thuong):
#   BTCDOMUSDT = chi so thong tri BTC, USDCUSDT = stablecoin (khong bao gio pump)
EXCLUDE_SYMBOL_KEYWORDS = ("_", "USDC", "BTCDOM")

# False = GIU cac coin meme ten tieng Trung (vd 我踏马来了USDT, 龙虾USDT).
# Cac coin nay co that tren san va tung ra tin hieu, nen mac dinh khong loai.
EXCLUDE_NON_ASCII_SYMBOLS = False

# ---------------------------------------------------------------------------
# 3. NGUONG PASS F1 - F6
# ---------------------------------------------------------------------------
# PRESET tieu chi:
#   "SCREENSHOT" - theo anh tin hieu that cua bot goc (RSI6/12/24, F4 +5%/3 chu ky).
#                  Anh mau: "F1: PASS - RSI6(15m)=70.05, RSI12(4h)=78.3, RSI24(1D)=67.81"
#                  va "F4: FAIL - OI did not increase by 5% over the last 3 periods".
#   "PDF"        - theo tai liec Cach_thuc_Bot_SHORT... (RSI14, nguong 90/80/65, F4 +8%).
FILTER_PRESET = "SCREENSHOT"

if FILTER_PRESET == "PDF":
    # F1 - RSI qua mua da khung (RAT QUAN TRONG)
    RSI_PERIODS = {"15m": 14, "4h": 14, "1d": 14}
    F1_RSI_15M_PASS = 90.0
    F1_RSI_4H_PASS = 80.0
    F1_RSI_1D_PASS = 65.0
    # F4 - Open Interest tang (RAT QUAN TRONG)
    F4_OI_CHANGE_PASS = 8.0         # % (mau KGEN +9.1% da PASS -> cau hinh ~8%)
    F4_OI_LOOKBACK_15M_BARS = 4     # so nen 15m nhin lai = 1 gio
else:  # SCREENSHOT
    RSI_PERIODS = {"15m": 6, "4h": 12, "1d": 24}
    F1_RSI_15M_PASS = 70.0
    F1_RSI_4H_PASS = 70.0
    F1_RSI_1D_PASS = 65.0
    F4_OI_CHANGE_PASS = 5.0         # anh: "did not increase by 5%"
    F4_OI_LOOKBACK_15M_BARS = 3     # anh: "over the last 3 periods"

RSI_PERIOD = 14                     # fallback khi goi rsi() khong truyen period

# F2 - Long/Short account ratio (QUAN TRONG)
F2_LONG_RATIO_PASS = 65.0           # % tai khoan Long

# F3 - Spike nen 15m (QUAN TRONG)
# PDF ghi 7%; anh mau CHILLGUYUSDT PASS voi 6.1% -> preset SCREENSHOT dung 5%.
F3_SPIKE_15M_PASS = 7.0 if FILTER_PRESET == "PDF" else 5.0

# F5 - Upper wick / rau nen tren (XAC NHAN)
F5_UPPER_WICK_RATIO_PASS = 0.30     # rau tren / bien do nen
F5_WICK_LOOKBACK_BARS = 2           # xet 2 nen 15m gan nhat

# F6 - Funding rate (HARD FILTER)
F6_FUNDING_MIN = -0.15              # %: funding phai >= -0.15%

# ---------------------------------------------------------------------------
# 4. THANG DIEM 100 (phan bo theo cot "Muc do" trong PDF)
# ---------------------------------------------------------------------------
WEIGHTS = {
    "rsi_15m": 12.0,    # F1 - Rat quan trong (tong F1 = 30)
    "rsi_4h": 10.0,
    "rsi_1d": 8.0,
    "oi": 20.0,         # F4 - Rat quan trong
    "long_ratio": 15.0,  # F2 - Quan trong
    "spike": 15.0,      # F3 - Quan trong
    "funding": 12.0,    # F6 - Hard filter
    "upper_wick": 8.0,  # F5 - Xac nhan
}                        # Tong = 100.0

# Ramp cham diem tung phan: (gia tri 0 diem, gia tri full diem)
# Nho partial credit nen coin gan nguong van co diem -> co the dat 50/100.
RAMPS = {
    "rsi_15m": (F1_RSI_15M_PASS - 20.0, F1_RSI_15M_PASS),
    "rsi_4h": (F1_RSI_4H_PASS - 20.0, F1_RSI_4H_PASS),
    "rsi_1d": (F1_RSI_1D_PASS - 15.0, F1_RSI_1D_PASS),
    "oi": (2.0, F4_OI_CHANGE_PASS),
    "long_ratio": (50.0, F2_LONG_RATIO_PASS),
    "spike": (3.0, F3_SPIKE_15M_PASS),
    "funding": (-0.30, F6_FUNDING_MIN),
    "upper_wick": (0.15, F5_UPPER_WICK_RATIO_PASS),
}

# PDF: "F1 va F6 nen la dieu kien bat buoc".
# True  -> chi bao coin PASS ca F1 va F6 (dung logic vao lenh cua PDF).
# False -> bao MOI coin >= MIN_SCORE, coin F1/F6 FAIL bi danh nhan WAIT.
REQUIRE_MANDATORY_PASS = False

# Dieu kien de gan nhan SHORT (thay vi WAIT):
#   "ALL"       - phai PASS ca 6 tieu chi F1-F6. Dung theo anh mau: CHILLGUYUSDT
#                 PASS F1,F2,F5,F6 nhung FAIL F4 -> van la "C - WAIT".
#   "MANDATORY" - chi can PASS F1 va F6 (theo cau khuyen nghi trong PDF).
SHORT_REQUIRES = "ALL"

# Cach xep hang (grade):
#   "SIMPLE"   - giong bot goc: PASS het 6 -> A+/A, con thieu bat ky tieu chi -> C.
#                (anh mau CHILLGUYUSDT 5/6 PASS van ghi "C", PDF: TSTUSDT -> "C")
#   "DETAILED" - chia nho A+/A/B+/B/C+/C theo diem de de xep uu tien theo doi.
GRADE_MODE = "SIMPLE"

# Hien thi diem tren thang 10 (giong anh: "Score: 8/10") ben canh thang 100.
TELEGRAM_SHOW_SCORE_10 = True

# ---------------------------------------------------------------------------
# 5. ENTRY / SL / TP (cong thuc muc 4-6 cua PDF)
# ---------------------------------------------------------------------------
# Preset Entry/SL/TP:
#   "SCREENSHOT" - theo anh tin hieu that: SL +1.5%, TP = 2.5R / 5R / 7.5R
#                  (vd Entry 0.013297 -> SL 0.0135, TP 0.0128 / 0.0123 / 0.0118)
#   "PDF"        - theo tai lieu: SL +1.3%, TP -3.5% / -9.8% / -15%
LEVELS_PRESET = "SCREENSHOT"

if LEVELS_PRESET == "PDF":
    SL_PCT = 1.3                        # % tren Entry
    TP_R_MULTIPLES: tuple[float, ...] = ()   # khong dung R, dung % co dinh
    TP_PCTS = (3.5, 9.8, 15.0)          # % duoi Entry
else:  # SCREENSHOT
    SL_PCT = 1.5                        # anh: 0.013297 -> 0.0135 = +1.53%
    TP_R_MULTIPLES = (2.5, 5.0, 7.5)    # TP tinh theo boi so rui ro (R)
    TP_PCTS = (3.75, 7.5, 11.25)        # = R x 1.5% (khop so trong anh)

SL_MULTIPLIER = 1.0 + SL_PCT / 100.0
TP_MULTIPLIERS = tuple(1.0 - p / 100.0 for p in TP_PCTS)

# ---------------------------------------------------------------------------
# 6. BINANCE API (public endpoint, KHONG can API key)
# ---------------------------------------------------------------------------
FAPI_BASE = "https://fapi.binance.com"
REQUEST_TIMEOUT = 20
MAX_RETRIES = 3
RETRY_BACKOFF = 1.5
MAX_WORKERS = 12                    # so luong request song song

# QUAN TRONG ve weight cua /fapi/v1/klines:
#   limit <= 100  -> weight 1
#   limit 101-500 -> weight 2 (thuc te do duoc 4)
# Dung 100 giup giam 4 lan weight, van du nen cho RSI 6/12/24.
KLINES_LIMIT = 100

# Gioi han weight moi phut cua Binance Futures (that su la 2400).
# De o muc thap hon de con cho cac request khac + tranh 418/429.
MAX_WEIGHT_PER_MINUTE = 2000

# Nghi giua cac request. Voi 524 coin, dat 0 va dua vao rate limiter ben duoi.
THROTTLE_SECONDS = 0.0

# ---------------------------------------------------------------------------
# 7. OUTPUT
# ---------------------------------------------------------------------------
CSV_DIR = "signals"
LOG_FILE = "bot.log"

# ---------------------------------------------------------------------------
# 8. TELEGRAM
# ---------------------------------------------------------------------------
# De trong -> bo qua Telegram, chi in ra console + CSV.
TELEGRAM_BOT_TOKEN = "8845676457:AAEasgAmUmaCG9IUB0IEGDhESzF_TOm35-E"

# Chat/group nhan thong bao. De trong cung duoc: moi nguoi chi can gui /start
# cho bot, chat_id se tu dong duoc luu vao TELEGRAM_SUBSCRIBERS_FILE.
TELEGRAM_CHAT_ID = ""

# File luu danh sach chat_id da /start (nhan thong bao tu dong moi 5 phut).
TELEGRAM_SUBSCRIBERS_FILE = "telegram_subscribers.json"

# --- Lang nghe lenh nguoi dung (/search, /top, /status ...) --------------
TELEGRAM_ENABLE_COMMANDS = True      # bat thread lang nghe lenh
TELEGRAM_POLL_TIMEOUT = 30           # long polling getUpdates (giay)
TELEGRAM_SEARCH_TOP_LIMIT = 10       # so coin toi da cho lenh /top

# True: ai gui bat ky lenh nao cho bot cung duoc tu dong nhan canh bao 5 phut
# (khong can go /start). Go /stop de huy.
TELEGRAM_AUTO_SUBSCRIBE = True

# --- Hoat dong trong NHOM (group / supergroup) ---------------------------
# Tu dong dang ky nhom nhan canh bao ngay khi bot duoc add vao nhom.
TELEGRAM_AUTO_SUBSCRIBE_GROUP = True

# Trong nhom, reply truc tiep vao tin nhan cua nguoi go lenh (de biet tra loi ai).
TELEGRAM_REPLY_IN_GROUP = True

# Trong nhom, tag ten nguoi go lenh o dau cau tra loi.
TELEGRAM_MENTION_USER_IN_GROUP = True

# Trong nhom, chi ADMIN duoc phep go /stop (tranh 1 nguoi tat canh bao ca nhom).
TELEGRAM_GROUP_ADMIN_ONLY_STOP = True

# Trong nhom, KHONG gui tin "Dang lay du lieu..." de bot lam nhieu chat.
TELEGRAM_GROUP_SHOW_LOADING = False

# Chong spam: moi nguoi phai cho bao nhieu giay giua 2 lenh (0 = tat).
TELEGRAM_USER_COOLDOWN_SECONDS = 3

# Chi coi tin nhan thuong (khong co dau '/') la ten coin khi o CHAT RIENG.
# De True se an toan: bot khong tra loi moi cau chat trong nhom.
TELEGRAM_PLAIN_TEXT_PRIVATE_ONLY = True

# Ten hien thi tren dau moi tin nhan (giong "MMisMyEx" trong anh mau).
TELEGRAM_HEADER_NAME = "Bot_v1_byTuanAnh"

# --- Dieu kien day tin nhan Telegram ------------------------------------
# Chi day coin co it nhat N tieu chi PASS trong F1-F6.
#   4 = chat luong tot, moi vong chi con vai coin dang chu y (KHUYEN NGHI)
#   2 = day rong hon nhung rat nhieu tin
TELEGRAM_MIN_PASSED_FILTERS = 4

# Sap xep uu tien khi day tin (coin manh nhat len dau):
#   "PASS_THEN_SCORE" - nhieu tieu chi PASS truoc, roi den diem cao  (mac dinh)
#   "SCORE_THEN_PASS" - diem cao truoc, roi den so tieu chi PASS
#   "SCORE"           - chi theo diem
TELEGRAM_SORT_MODE = "PASS_THEN_SCORE"

# Danh so thu tu #1 #2 #3... vao tin nhan de biet coin nao manh nhat vong quet.
TELEGRAM_SHOW_RANK = True

# Hien dong tom tat "da quet N coin" tren dau tin nhan.
TELEGRAM_SHOW_SCAN_SUMMARY = True

# Neu True: chi day khi diem cung >= MIN_SCORE. False = chi can du so tieu chi PASS.
TELEGRAM_ALSO_REQUIRE_MIN_SCORE = False

# Diem toi thieu de day Telegram (0 = khong ap dung).
# Thuc te tren san: rat nhieu coin PASS san F5+F6 (rau nen + funding duong) nen
# neu chi dung dieu kien ">= 2 PASS" se co ~20 tin/vong quet. Dat nguong diem
# nay giup bo bot tin rac ma van giu dung tieu chi ">= 2 PASS".
TELEGRAM_MIN_SCORE_FLOOR = 0.0

# Neu khong rong: coin phai PASS it nhat 1 trong cac bo loc nay moi duoc day.
# Vi du ("F1", "F2", "F3", "F4") = bo qua coin chi PASS F5+F6 (2 tieu chi de nhat).
TELEGRAM_REQUIRE_ANY_OF: tuple[str, ...] = ()

# So tin nhan toi da moi vong quet.
# Quet toan bo 524 coin nen chi lay TOP 3-4 coin manh nhat de khong spam.
TELEGRAM_MAX_MESSAGES_PER_SCAN = 4

# Khong gui lai cung 1 coin trong vong bao nhieu phut (chong spam).
TELEGRAM_COOLDOWN_MINUTES = 30

# Gui rieng tung coin 1 tin nhan (giong anh mau) thay vi gop 1 tin nhan dai.
TELEGRAM_ONE_MESSAGE_PER_COIN = True

# Nghi giua 2 tin nhan (giay) de tranh loi 429 cua Telegram.
TELEGRAM_SEND_DELAY = 1.2

# File luu thoi diem gui gan nhat cua tung coin (de cooldown song sot khi restart).
TELEGRAM_STATE_FILE = "telegram_sent.json"
