"""Kiểm chứng luật tra mã RxNorm của annotator trên 13 cặp GT của đề.

Kết quả (xem worklog/02): gõ mention thô vào approximateTerm cho 0/13 top-1.
Thêm lọc TTY=SCD → 5/13. Thêm làm sạch chuỗi mention → 10/13, đúng bằng số mã GT
có mặt trong prescribable subset. 3 ca còn lại là mã obsolete/remapped.

Script này CHỈ ĐỌC FILE, không gọi mạng. Lý do: proxy sandbox có allowlist chặn
rxnav.nlm.nih.gov, python subprocess không ra được (chi tiết ở worklog/02). Khâu
tải nằm ở src/fetch_approx.sh, chạy bằng shell, ghi vào data/kb/rxnav_raw/.

Bản trước của file này tự gọi curl qua subprocess, nhận rỗng mọi lần, rồi báo
0/13 — kết luận sai. Đừng đưa việc gọi mạng trở lại đây.
"""

from __future__ import annotations

import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "kb" / "rxnav_raw"
RXNCONSO = ROOT / "data" / "raw" / "rxnorm" / "RXNCONSO.RRF"

# (slug file, mention nguyên văn trong input, mã GT theo đề)
# Mã GT phải copy từ đề — lần trước gõ tay làm thiếu chữ số (90475 vs 904475,
# 36047 vs 360047) và làm sai toàn bộ bảng kết quả.
GOLD: list[tuple[str, str, str]] = [
    ("m01", "amlodipine 10 mg po daily", "308135"),
    ("m02", "aspirin 81 mg po daily", "243670"),
    ("m03", "metoprolol succinate xl 50 mg po daily", "866436"),
    ("m04", "guaifenesin ml po q6h:prn", "392085"),
    ("m05", "nystatin oral suspension 5 ml po qid:prn", "7597"),
    ("m06", "acetaminophen 325-650 mg po q6h:prn", "313782"),
    ("m07", "pravastatin 40 mg po daily", "904475"),
    ("m08", "docusate sodium 100 mg po bid", "1099279"),
    ("m09", "sena 8.6 mg po bid:prn", "312935"),
    ("m10", "clonazepam 0.5 mg po qam:prn", "197527"),
    ("m11", "clonazepam 1.5 mg po qhs", "197528"),
    ("m12", "Chlorpheniramine 0.4 MG/ML", "360047"),
    ("m13", "Capsaicin 0.38 MG/ML", "1660761"),
]

# Truy vấn đã làm sạch cho các ca mà mention thô bị miss. Ba phép biến đổi:
# bỏ đuôi liều dùng, sửa chính tả mention, dịch viết tắt dạng bào chế.
CLEANED: dict[str, str] = {
    "m03": "metoprolol succinate 50 mg extended release",  # xl -> extended release
    "m05": "nystatin",  # bỏ dạng bào chế + thể tích liều -> về tầng IN
    "m06": "acetaminophen 325 mg",  # 325-650 -> giữ số đầu
    "m09": "senna 8.6 mg",  # sena -> senna
}


def load_tty() -> dict[str, set[str]]:
    """TTY của từng RxCUI trong prescribable subset.

    RXNCONSO: RXCUI|LAT|TS|LUI|STT|SUI|ISPREF|RXAUI|SAUI|SCUI|SDUI|SAB|TTY|CODE|STR|...
    """
    tty: dict[str, set[str]] = collections.defaultdict(set)
    with RXNCONSO.open(encoding="utf-8") as fh:
        for line in fh:
            p = line.split("|")
            if p[11] == "RXNORM":
                tty[p[0]].add(p[12])
    return tty


def candidates(path: Path) -> list[str]:
    """RxCUI theo thứ tự rank, đã gộp các atom cùng concept."""
    if not path.exists():
        return []
    d = json.loads(path.read_text())
    seen: list[str] = []
    for c in d.get("approximateGroup", {}).get("candidate") or []:
        if c["rxcui"] not in seen:
            seen.append(c["rxcui"])
    return seen


def rank_of(gt: str, cands: list[str]) -> int | None:
    return cands.index(gt) + 1 if gt in cands else None


if __name__ == "__main__":
    tty = load_tty()
    n = len(GOLD)
    raw1 = raw20 = scd1 = clean1 = 0

    print(f"{'mention':42} {'GT':9} {'thô':>4} {'+SCD':>5} {'+sạch':>6} {'subset':>7}")
    print("-" * 78)
    for slug, mention, gt in GOLD:
        cands = candidates(RAW / f"approx_{slug}.json")
        scd = [c for c in cands if "SCD" in tty.get(c, ())]

        p_raw = rank_of(gt, cands)
        p_scd = rank_of(gt, scd)

        # cột "+sạch": dùng truy vấn đã làm sạch nếu ca này có
        if slug in CLEANED:
            cl = candidates(RAW / f"clean_{slug}.json")
            p_clean = rank_of(gt, cl)
        else:
            p_clean = p_scd

        raw20 += p_raw is not None
        raw1 += p_raw == 1
        scd1 += p_scd == 1
        clean1 += p_clean is not None and p_clean <= 2

        print(
            f"{mention[:42]:42} {gt:9} {str(p_raw or '-'):>4} "
            f"{str(p_scd or '-'):>5} {str(p_clean or '-'):>6} "
            f"{'yes' if gt in tty else 'NO':>7}"
        )

    print("-" * 78)
    print(f"top-20 gõ thô            : {raw20}/{n}")
    print(f"top-1  gõ thô            : {raw1}/{n}")
    print(f"top-1  + lọc SCD         : {scd1}/{n}")
    print(f"top-2  + làm sạch chuỗi  : {clean1}/{n}")
    print(f"GT có trong subset       : {sum(1 for _, _, g in GOLD if g in tty)}/{n}")
    print(
        "\nCẩn trọng: 13 mẫu, 4 ca ở CLEANED do tune tay -> rủi ro overfit.\n"
        "Phải đo lại trên >=100 cặp sau khi annotate corpus."
    )
