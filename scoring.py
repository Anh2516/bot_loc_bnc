"""
Cham diem bo loc F1-F6 tren thang 100 diem.

Phan bo diem theo cot "Muc do" trong PDF (xem config.WEIGHTS):
  F1 RSI da khung : 30 (15m=12, 4H=10, 1D=8)  - Rat quan trong
  F4 Open Interest: 20                        - Rat quan trong
  F2 Long ratio   : 15                        - Quan trong
  F3 Spike 15m    : 15                        - Quan trong
  F6 Funding      : 12                        - Hard filter
  F5 Upper wick   :  8                        - Xac nhan

Moi tieu chi duoc cham diem tung phan (partial credit) theo ramp tuyen tinh
trong config.RAMPS: duoi nguong thap = 0 diem, dat nguong PASS = full diem.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import config
import indicators


def _ramp_score(value: float | None, key: str) -> float:
    """Cham diem tuyen tinh cho 1 tieu chi. value=None -> 0 diem (thieu du lieu)."""
    weight = config.WEIGHTS[key]
    if value is None:
        return 0.0
    low, high = config.RAMPS[key]
    if high == low:
        ratio = 1.0 if value >= high else 0.0
    else:
        ratio = (value - low) / (high - low)
    return weight * max(0.0, min(1.0, ratio))


@dataclass
class FilterResult:
    """Ket qua 1 bo loc F1..F6."""

    code: str
    name: str
    importance: str
    passed: bool
    score: float
    max_score: float
    detail: str          # dang ngan gon cho bang console
    reason: str = ""     # dang mo ta day du cho tin nhan Telegram (giong anh mau)


@dataclass
class CoinScore:
    """Ket qua cham diem day du cho 1 coin."""

    symbol: str
    price: float
    total_score: float
    grade: str
    action: str            # "SHORT" hoac "WAIT"
    trap_risk: float
    filters: list[FilterResult] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    levels: dict[str, float] = field(default_factory=dict)
    rank: int = 0            # thu tu uu tien trong vong quet (1 = manh nhat)
    rank_total: int = 0      # tong so coin duoc chon trong vong quet
    scanned_total: int = 0   # tong so coin da quet trong vong do (vd 524)

    @property
    def score_10(self) -> float:
        """Diem tren thang 10 (giong 'Score: 8/10' trong anh tin hieu goc)."""
        return round(self.total_score / 10.0, 1)

    @property
    def failed_mandatory(self) -> list[str]:
        """Danh sach bo loc bat buoc (F1, F6) bi FAIL."""
        return [f.code for f in self.filters if f.code in ("F1", "F6") and not f.passed]

    @property
    def passed_all(self) -> bool:
        return all(f.passed for f in self.filters)

    @property
    def passed_count(self) -> int:
        """So tieu chi PASS trong F1-F6 (dung cho dieu kien day Telegram)."""
        return sum(1 for f in self.filters if f.passed)

    @property
    def failed_codes(self) -> list[str]:
        """Danh sach ma bo loc bi FAIL, vd ['F3', 'F4']."""
        return [f.code for f in self.filters if not f.passed]


def _grade(score: float, mandatory_ok: bool, passed_all: bool) -> str:
    """
    Xep hang theo cac vi du that:
      * KGENUSDT   : F1-F6 full PASS      -> A+
      * CHILLGUY   : FAIL F3+F4 (4/6)     -> C  (anh mau ghi "C - WAIT")
      * TSTUSDT    : FAIL F1+F6           -> C
    Coin chua PASS het 6 tieu chi thi khong bao gio duoc hang A.
    """
    if passed_all:
        return "A+" if score >= 85 else "A"

    # SIMPLE: giong bot goc - thieu bat ky tieu chi nao deu la "C"
    if config.GRADE_MODE == "SIMPLE":
        return "C"

    # DETAILED: chia nho de de xep uu tien theo doi
    if mandatory_ok and score >= 85:
        return "B+"
    if mandatory_ok and score >= 70:
        return "B"
    if score >= 50:
        return "C+"
    return "C"


def _trap_risk(metrics: dict[str, Any]) -> float:
    """
    Trap Risk 0-10: rui ro bi long squeeze / bay gia khi short.
    Cang nhieu yeu to "con du dia pump" thi risk cang cao.
    """
    risk = 5.0
    funding = metrics.get("funding")
    long_ratio = metrics.get("long_ratio")
    oi_change = metrics.get("oi_change")
    rsi_1d = metrics.get("rsi_1d")
    wick = metrics.get("upper_wick")

    if funding is not None:
        if funding > 0.05:
            risk += 1.0      # funding duong cao -> long tra phi, de bi xa
        elif funding < -0.10:
            risk += 1.5      # funding am -> short da dong, de bi squeeze
    if long_ratio is not None and long_ratio >= 70:
        risk += 1.0
    if oi_change is not None and oi_change >= 15:
        risk += 1.0          # OI tang qua manh -> dong tien vao rat manh
    if rsi_1d is not None and rsi_1d >= 80:
        risk += 0.5          # xu huong ngay qua manh -> short nguoc trend
    if wick is not None and wick >= config.F5_UPPER_WICK_RATIO_PASS:
        risk -= 0.5          # da co luc ban tu choi gia -> giam rui ro
    return round(max(0.0, min(10.0, risk)), 1)


def _fmt(value: float | None, suffix: str = "%", nd: int = 2) -> str:
    return "n/a" if value is None else f"{value:.{nd}f}{suffix}"


# ---------------------------------------------------------------------------
# Mo ta ly do PASS/FAIL theo dung van phong tin nhan cua bot goc (anh mau), vd:
#   "F1: PASS - RSI6(15m)=70.05, RSI12(4h)=78.3, RSI24(1D)=67.81"
#   "F4: FAIL - OI did not increase by 5% over the last 3 periods (2.5M to 2.6M)"
# ---------------------------------------------------------------------------
def _reason_f1(m: dict[str, Any], passed: bool) -> str:
    p = m.get("rsi_periods") or config.RSI_PERIODS
    txt = (
        f"RSI{p['15m']}(15m)={_fmt(m.get('rsi_15m'), '', 2)}, "
        f"RSI{p['4h']}(4h)={_fmt(m.get('rsi_4h'), '', 1)}, "
        f"RSI{p['1d']}(1D)={_fmt(m.get('rsi_1d'), '', 2)}"
    )
    if passed:
        return txt
    need = (
        f"{config.F1_RSI_15M_PASS:.0f}/{config.F1_RSI_4H_PASS:.0f}"
        f"/{config.F1_RSI_1D_PASS:.0f}"
    )
    return f"{txt}; chua dat nguong {need}"


def _reason_f2(m: dict[str, Any], passed: bool) -> str:
    lr = m.get("long_ratio")
    if lr is None:
        return "khong co du lieu Long/Short ratio"
    if passed:
        return f"L/S long ratio={lr:.1f}%"
    return (
        f"L/S long ratio={lr:.1f}% < {config.F2_LONG_RATIO_PASS:.0f}%, "
        "dam dong chua nghieng Long du manh"
    )


def _reason_f3(m: dict[str, Any], passed: bool) -> str:
    spike, t = m.get("spike"), m.get("spike_time")
    at = f" at {t} UTC" if t else ""
    if spike is None:
        return "khong tinh duoc spike nen 15m"
    if passed:
        return f"Spike with 15m candle{at} increased by {spike:.1f}%"
    return (
        f"No 15m spike >= {config.F3_SPIKE_15M_PASS:.0f}%"
        f" (cao nhat{at} chi {spike:.1f}%)"
    )


def _reason_f4(m: dict[str, Any], passed: bool) -> str:
    oi = m.get("oi_change")
    periods = m.get("oi_periods") or config.F4_OI_LOOKBACK_15M_BARS
    v_from = indicators.format_compact(m.get("oi_value_from"))
    v_to = indicators.format_compact(m.get("oi_value_to"))
    rng = f" ({v_from} to {v_to})" if m.get("oi_value_to") else ""
    if oi is None:
        return "khong co du lieu Open Interest"
    if passed:
        return (
            f"OI increased by {oi:.1f}% over the last {periods} periods{rng}"
        )
    return (
        f"OI did not increase by {config.F4_OI_CHANGE_PASS:.0f}% over the last"
        f" {periods} periods{rng}"
    )


def _reason_f5(m: dict[str, Any], passed: bool) -> str:
    wick, t = m.get("upper_wick"), m.get("upper_wick_time")
    at = f" at {t} UTC" if t else ""
    if wick is None:
        return "khong tinh duoc rau nen tren"
    if passed:
        return f"Upper wick seen{at} (ratio {wick:.2f})"
    return (
        f"No significant upper wick (ratio {wick:.2f}"
        f" < {config.F5_UPPER_WICK_RATIO_PASS:.2f})"
    )


def _reason_f6(m: dict[str, Any], passed: bool) -> str:
    fr = m.get("funding")
    if fr is None:
        return "khong co du lieu funding rate"
    if passed:
        sign = "not negative" if fr >= 0 else "chua am qua sau"
        return f"Funding rate is {fr:.3f}%, {sign}"
    return (
        f"Funding rate is {fr:.3f}%, am hon nguong"
        f" {config.F6_FUNDING_MIN}% - thi truong da qua dong Short"
    )


def score_coin(symbol: str, metrics: dict[str, Any]) -> CoinScore:
    """Ap dung F1-F6, tra ve CoinScore voi tong diem tren thang 100."""
    rsi_15m = metrics.get("rsi_15m")
    rsi_4h = metrics.get("rsi_4h")
    rsi_1d = metrics.get("rsi_1d")
    long_ratio = metrics.get("long_ratio")
    spike = metrics.get("spike")
    oi_change = metrics.get("oi_change")
    wick = metrics.get("upper_wick")
    funding = metrics.get("funding")

    # --- F1: RSI qua mua da khung (tong 30 diem) ---
    f1_score = (
        _ramp_score(rsi_15m, "rsi_15m")
        + _ramp_score(rsi_4h, "rsi_4h")
        + _ramp_score(rsi_1d, "rsi_1d")
    )
    f1_pass = (
        rsi_15m is not None and rsi_15m >= config.F1_RSI_15M_PASS
        and rsi_4h is not None and rsi_4h >= config.F1_RSI_4H_PASS
        and rsi_1d is not None and rsi_1d >= config.F1_RSI_1D_PASS
    )

    f2_score = _ramp_score(long_ratio, "long_ratio")
    f2_pass = long_ratio is not None and long_ratio >= config.F2_LONG_RATIO_PASS

    f3_score = _ramp_score(spike, "spike")
    f3_pass = spike is not None and spike >= config.F3_SPIKE_15M_PASS

    f4_score = _ramp_score(oi_change, "oi")
    f4_pass = oi_change is not None and oi_change >= config.F4_OI_CHANGE_PASS

    f5_score = _ramp_score(wick, "upper_wick")
    f5_pass = wick is not None and wick >= config.F5_UPPER_WICK_RATIO_PASS

    f6_score = _ramp_score(funding, "funding")
    f6_pass = funding is not None and funding >= config.F6_FUNDING_MIN

    w = config.WEIGHTS
    filters = [
        FilterResult(
            "F1", "RSI 15m/4H/1D", "Rat quan trong", f1_pass, f1_score,
            w["rsi_15m"] + w["rsi_4h"] + w["rsi_1d"],
            f"RSI15m={_fmt(rsi_15m, '', 1)} 4H={_fmt(rsi_4h, '', 1)}"
            f" 1D={_fmt(rsi_1d, '', 1)} (can >="
            f"{config.F1_RSI_15M_PASS:.0f}/{config.F1_RSI_4H_PASS:.0f}"
            f"/{config.F1_RSI_1D_PASS:.0f})",
            _reason_f1(metrics, f1_pass),
        ),
        FilterResult(
            "F2", "Long/Short Ratio", "Quan trong", f2_pass, f2_score, w["long_ratio"],
            f"Long={_fmt(long_ratio)} (can >={config.F2_LONG_RATIO_PASS:.0f}%)",
            _reason_f2(metrics, f2_pass),
        ),
        FilterResult(
            "F3", "Spike nen 15m", "Quan trong", f3_pass, f3_score, w["spike"],
            f"Spike15m={_fmt(spike)} (can >={config.F3_SPIKE_15M_PASS:.0f}%)",
            _reason_f3(metrics, f3_pass),
        ),
        FilterResult(
            "F4", "Open Interest", "Rat quan trong", f4_pass, f4_score, w["oi"],
            f"OI 1h={_fmt(oi_change)} (can >={config.F4_OI_CHANGE_PASS:.0f}%)",
            _reason_f4(metrics, f4_pass),
        ),
        FilterResult(
            "F5", "Upper Wick", "Xac nhan", f5_pass, f5_score, w["upper_wick"],
            f"wick_ratio={_fmt(wick, '', 2)}"
            f" (can >={config.F5_UPPER_WICK_RATIO_PASS:.2f})",
            _reason_f5(metrics, f5_pass),
        ),
        FilterResult(
            "F6", "Funding Rate", "Hard filter", f6_pass, f6_score, w["funding"],
            f"Funding={_fmt(funding, '%', 4)} (can >={config.F6_FUNDING_MIN}%)",
            _reason_f6(metrics, f6_pass),
        ),
    ]

    total = round(sum(f.score for f in filters), 2)
    mandatory_ok = f1_pass and f6_pass
    passed_all = all(f.passed for f in filters)

    # Nhan SHORT/WAIT: theo anh mau, thieu du 1 tieu chi (F4) van la WAIT
    # -> mac dinh SHORT_REQUIRES = "ALL". Dat "MANDATORY" de chi can F1+F6.
    if config.SHORT_REQUIRES == "MANDATORY":
        action = "SHORT" if mandatory_ok else "WAIT"
    else:
        action = "SHORT" if passed_all else "WAIT"

    return CoinScore(
        symbol=symbol,
        price=float(metrics.get("price") or 0.0),
        total_score=total,
        grade=_grade(total, mandatory_ok, passed_all),
        action=action,
        trap_risk=_trap_risk(metrics),
        filters=filters,
        metrics=metrics,
    )
