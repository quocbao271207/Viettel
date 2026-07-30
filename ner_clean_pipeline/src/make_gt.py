"""Hand-annotated ground truth for a few files, written as JSON.

Purpose: calibrate `src/score.py`. The scoring formula is known exactly
(worklog/03), but *how BTC pairs* a predicted entity with a GT entity is not.
`score.py` computes every plausible pairing variant; whichever variant
reproduces the known submission-#1 numbers (WER 82.9421 / J_assertion 18.5774 /
J_candidates 13.9879) is the real one.

Annotations are written as (needle, occurrence_index, type, assertions,
candidates) rather than raw offsets, so a typo produces a hard failure instead
of a silently wrong span. Offsets are resolved by searching the NFC-normalised
text and mapping back to raw offsets via `textnorm`, because 20 input files are
in NFD form (see worklog/04).

Annotation conventions followed (from the problem statement's round-1 example):
  - `assertions` applies only to CHẨN_ĐOÁN / THUỐC / TRIỆU_CHỨNG.
  - Everything under a "Tiền sử bệnh" section is `isHistorical`, by section
    scope, not by sentence cue.
  - In the example, a symptom naming a drug's indication ("điều trị lo âu")
    keeps `assertions: []` even though the drug itself is isHistorical. So a
    symptom is only marked when the symptom itself is historical/negated.
  - `candidates` only for CHẨN_ĐOÁN (ICD-10) and THUỐC (RxNorm).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from textnorm import normalize, to_raw_span  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DX, SYM, DRUG, LAB, VAL = "CHẨN_ĐOÁN", "TRIỆU_CHỨNG", "THUỐC", "TÊN_XÉT_NGHIỆM", "KẾT_QUẢ_XÉT_NGHIỆM"

# (needle, nth occurrence starting at 0, type, assertions, candidates)
A = tuple[str, int, str, list[str], list[str]]

GT: dict[str, list[A]] = {}

# --------------------------------------------------------------------- 95.txt
# QA thầy thuốc về gút + một mục "Tiền sử bệnh lý" ghép vào cuối.
# M10 có 66 mã con -> KHÔNG bung con (xem worklog/01). Trả mã cha M10.
GT["95"] = [
    ("bệnh gút", 0, DX, [], ["M10"]),
    ("khỏi đau", 0, SYM, ["isHistorical"], []),
    ("bệnhgout", 0, DX, [], ["M10"]),
    ("hạt tophi", 0, DX, [], ["M10"]),
    ("hạt tophi", 1, DX, [], ["M10"]),
    ("hạt tophi", 2, DX, [], ["M10"]),
    ("sưng", 0, SYM, [], []),
    ("tấy đỏ", 0, SYM, [], []),
    ("hạt tophi", 3, DX, [], ["M10"]),
    ("hoại tử", 0, DX, [], []),
    ("biến dạng xương khớp", 0, DX, [], []),
    ("nhiễm trùng máu", 0, DX, [], ["A41.9"]),
    ("hạt tophi", 4, DX, [], ["M10"]),
    ("gout cấp", 0, DX, [], ["M10"]),
    ("đau các khớp", 0, SYM, [], []),
    # mục "1. Tiền sử bệnh lý" -> isHistorical theo section
    ("đái tháo đường", 0, DX, ["isHistorical"], ["E14"]),
    ("tăng huyết áp", 0, DX, ["isHistorical"], ["I10"]),
    ("béo phì", 0, DX, ["isHistorical"], ["E66.9"]),
    ("ngưng thở khi ngủ do tắc nghẽn", 0, DX, ["isHistorical"], ["G47.3"]),
    # mục "Thuốc trước khi nhập viện" -> isHistorical
    ("tylenol", 0, DRUG, ["isHistorical"], ["202433"]),
    ("mucinex d", 0, DRUG, ["isHistorical"], ["352777"]),
    ("tiêu chảy", 0, SYM, [], []),
]

# --------------------------------------------------------------------- 96.txt
# Block bệnh án (hẹp động mạch thận) + block tư vấn phun môi.
GT["96"] = [
    ("chụp cắt lớp vi tính (ct)", 0, LAB, [], []),
    ("tắc hẹp 80% động mạch thận trái", 0, DX, [], ["I70.1"]),
    ("chụp cắt lớp vi tính (ct)", 1, LAB, [], []),
    ("tắc hẹp 80% động mạch thận trái", 1, DX, [], ["I70.1"]),
    ("Môi bong vẩy trắng", 0, SYM, [], []),
    ("môi khô", 0, SYM, [], []),
    ("vitamin C", 0, DRUG, [], ["1151"]),
]

# --------------------------------------------------------------------- 97.txt
# Bệnh án suy thận mạn GĐ5 + chèn đoạn tư vấn bệnh trĩ. File NFD.
GT["97"] = [
    # mục "1. Tiền sử bệnh" -> isHistorical
    ("Suy thận mạn giai đoạn V", 0, DX, ["isHistorical"], ["N18.5"]),
    ("đái tháo đường", 0, DX, ["isHistorical"], ["E14"]),
    ("tăng huyết áp", 0, DX, ["isHistorical"], ["I10"]),
    ("u ác của tuyến tiền liệt", 0, DX, ["isHistorical"], ["C61"]),
    # VÙNG XÁM: mục "Tiền sử phẫu thuật / thủ thuật". Sinh thiết là thủ thuật lấy
    # mẫu ĐỂ xét nghiệm giải phẫu bệnh -> tính LAB. "Phẫu thuật cắt bỏ u" cùng mục
    # thì KHÔNG (điều trị, không phải xét nghiệm). Độ tin cậy vừa.
    ("Sinh thiết tuyến tiền liệt", 0, LAB, [], []),
    # mục "2. Bệnh sử hiện tại" -> hiện tại, không assertion
    ("mệt mỏi", 0, SYM, [], []),
    ("mất trí nhớ chi tiết", 0, SYM, [], []),
    ("khó chịu", 0, SYM, [], []),
    ("mệt mỏi", 1, SYM, [], []),
    ("ăn không ngon miệng", 0, SYM, [], []),
    ("ngứa da toàn thân", 0, SYM, [], []),
    ("mất trí nhớ chi tiết", 1, SYM, [], []),
    ("khó thở khi gắng sức", 0, SYM, [], []),
    ("buồn nôn", 0, SYM, [], []),
    ("nôn", 1, SYM, [], []),
    ("Mệt mỏi", 2, SYM, [], []),
    ("Ăn không ngon miệng", 1, SYM, [], []),
    ("Ngứa da toàn thân", 1, SYM, [], []),
    ("mất trí nhớ chi tiết", 2, SYM, [], []),
    ("bệnh trĩ", 0, DX, [], ["K64.9"]),
    ("Ure", 0, LAB, [], []),
    ("tăng từ [[69]] lên", 0, VAL, [], []),
    ("91 mg/dl", 0, VAL, [], []),
    ("24.6 -32.5 mmol/l", 0, VAL, [], []),
    ("photpho", 0, LAB, [], []),
    ("8.4", 0, VAL, [], []),
    ("u ác của tuyến tiền liệt", 1, DX, [], ["C61"]),
]

# --------------------------------------------------------------------- 98.txt
# Bệnh án tâm thần + chèn câu hỏi tàn nhang.
GT["98"] = [
    ("tàn nhang", 0, DX, [], ["L81.2"]),
    ("da sạm", 0, SYM, [], []),
    # "Mẹ Đã tử vong" -> isFamily
    ("Đã tử vong", 0, DX, ["isFamily"], []),
    # mục "Các bệnh mãn tính" trong Tiền sử bệnh -> isHistorical
    ("Rối loạn cảm xúc", 0, DX, ["isHistorical"], ["F39"]),
    ("Rối loạn lưỡng cực", 0, DX, ["isHistorical"], ["F31.9"]),
    ("rối loạn lo âu", 0, DX, ["isHistorical"], ["F41.9"]),
    # mục "Thuốc đã điều trị trước khi nhập viện" -> isHistorical
    ("klonopin", 0, DRUG, ["isHistorical"], ["202585"]),
    ("clonidine", 0, DRUG, ["isHistorical"], ["2599"]),
    ("clonidine", 1, DRUG, ["isHistorical"], ["2599"]),
    ("suboxone", 0, DRUG, ["isHistorical"], ["352990"]),
    ("ý định tự tử", 0, SYM, [], []),
    ("ý nghĩ tự bắn vào đầu", 0, SYM, [], []),
    ("trầm cảm", 0, DX, [], ["F32.9"]),
    ("hưng cảm", 0, DX, [], ["F30.9"]),
    ("tăng hoạt động", 0, SYM, [], []),
    ("giảm nhu cầu ngủ", 0, SYM, [], []),
    ("ý định tự tử", 1, SYM, [], []),
    ("suboxone", 1, DRUG, ["isHistorical"], ["352990"]),
    ("suboxone", 2, DRUG, ["isHistorical"], ["352990"]),
    ("ý nghĩ tự tử", 0, SYM, [], []),
    ("nghĩ tự bắn vào đầu", 1, SYM, [], []),
    ("lo âu", 1, SYM, [], []),
    ("hoảng sợ", 0, SYM, [], []),
    ("hoang tưởng", 0, SYM, [], []),
]

# --------------------------------------------------------------------- 99.txt
# Bệnh án: tiền sử + bệnh sử hiện tại + khám + chẩn đoán + CĐHA.
GT["99"] = [
    # mục "1. Tiền sử bệnh nội khoa" -> isHistorical
    ("viêm tủy xương", 0, DX, ["isHistorical"], ["M86.9"]),
    ("bàng quang thần kinh", 0, DX, ["isHistorical"], ["N31.9"]),
    ("liệt hai chi dưới", 0, DX, ["isHistorical"], ["G82.2"]),
    # mục "2. Bệnh sử hiện tại"
    ("biến đổi ý thức", 0, SYM, [], []),
    ("hạ thân nhiệt", 0, DX, [], ["T68"]),
    ("hạ huyết áp", 0, DX, [], ["I95.9"]),
    ("biến đổi ý thức", 1, SYM, [], []),
    ("hạ thân nhiệt", 1, DX, [], ["T68"]),
    ("hạ huyết áp", 1, DX, [], ["I95.9"]),
    ("huyết áp tâm thu là [[90]]", 0, VAL, [], []),
    ("biến đổi ý thức", 2, SYM, [], []),
    ("hạ thân nhiệt", 2, DX, [], ["T68"]),
    ("Khó thở khi nằm đầu bằng", 0, SYM, [], []),
    ("SpO2", 0, LAB, [], []),
    ("99%", 0, VAL, [], []),
    ("Tim nhịp không đều", 0, SYM, [], []),
    ("tần số", 0, LAB, [], []),
    ("105 chu  kì/phút", 0, VAL, [], []),
    ("Huyết áp", 3, LAB, [], []),
    ("110/70  mmHg", 0, VAL, [], []),
    ("rì rào phế nang giảm", 0, SYM, [], []),
    ("không có tiếng rales bệnh lí", 0, SYM, ["isNegated"], []),
    ("Không có điểm đau", 0, SYM, ["isNegated"], []),
    ("Không phù", 0, SYM, ["isNegated"], []),
    ("Đợt cấp COPD", 0, DX, [], ["J44.1"]),
    ("Tâm phế mạn", 0, DX, [], ["I27.9"]),
    ("Cơn tim nhanh nhĩ", 0, DX, [], ["I47.1"]),
    ("Nhiễm khuẩn đường tiêu hóa", 0, DX, [], ["A09.9"]),
    ("Tăng huyết áp", 0, DX, [], ["I10"]),
    ("chụp x-quang ngực", 0, LAB, [], []),
    ("không có hình ảnh tổn thương viêm cấp tính", 0, DX, ["isNegated"], []),
    # "so với chụp x-quang ngực trước đó" -> vẫn là xét nghiệm bệnh nhân đã làm
    ("chụp x-quang ngực", 1, LAB, [], []),
    # mục "Các thủ thuật đã thực hiện"
    ("cấy nước tiểu", 0, LAB, [], []),
    ("điện tâm đồ", 0, LAB, [], []),
    ("nhịp chậm xoang", 0, DX, [], ["R00.1"]),
    ("đường huyết lúc đói", 0, LAB, [], []),
    ("đường huyết thấp", 0, DX, [], []),
]

# -------------------------------------------------------------------- 100.txt
# QA sản khoa: aspirin dự phòng tiền sản giật. File NFD. Có 2 chỗ mask ***.
# Chỗ mask: coi là THUỐC không candidate — độ dài dấu sao khớp số ký tự gốc,
# nên span vẫn là một mention thuốc hợp lệ, chỉ không suy ra được RxCUI.
GT["100"] = [
    ("mang thai được 22 tuần", 0, SYM, [], []),
    ("nguy cơ tiền sản giật cao", 0, DX, [], ["O14"]),
    ("************", 0, DRUG, [], []),
    ("cục máu đông", 0, SYM, [], []),
    ("đi tiêu ra máu", 0, SYM, [], []),
    ("************", 1, DRUG, [], []),
    ("nguy cơ tiền sản giật cao", 1, DX, [], ["O14"]),
    ("tiền sản giật", 2, DX, [], ["O14"]),
    # "và những biến chứng liên quan đến tiền sản giật" -> vẫn nhắc bệnh, giữ
    # nhất quán với lần 2 ở trên
    ("tiền sản giật", 3, DX, [], ["O14"]),
    ("*******", 0, DRUG, [], []),
    ("chảy máu", 0, SYM, [], []),
    ("*******", 1, DRUG, [], []),
    ("lo lắng", 0, SYM, [], []),
    ("aspirin", 0, DRUG, [], ["1191"]),
    ("đại tiện ra máu đỏ tươi", 0, SYM, [], []),
]


def resolve(stem: str, ann: list[A]) -> list[dict]:
    """Turn (needle, nth, ...) annotations into entities with raw-text offsets."""
    raw = (ROOT / "input" / f"{stem}.txt").read_text(encoding="utf-8")
    norm, imap = normalize(raw)
    low = norm.lower()
    out: list[dict] = []
    for needle, nth, typ, asserts, cands in ann:
        # cú pháp "ngữ cảnh [[phần cần lấy]] ngữ cảnh": dò cả cụm dài cho khỏi
        # trùng lặp, nhưng span chỉ lấy phần trong [[ ]]. Cần cho những giá trị
        # ngắn như "90" xuất hiện nhiều nơi.
        pre = post = ""
        if "[[" in needle:
            pre, rest = needle.split("[[", 1)
            core, post = rest.split("]]", 1)
            needle = pre + core + post
            pre_len = len(normalize(pre)[0])
            core_len = len(normalize(core)[0])
        else:
            pre_len = 0
            core_len = None

        n = normalize(needle)[0].lower()
        starts: list[int] = []
        if set(needle) == {"*"}:
            # tên thuốc bị mask: khớp cả run dấu sao, không khớp substring bên
            # trong một run dài hơn (nếu không "*******" sẽ trúng vào giữa
            # "************")
            starts = [m.start() for m in re.finditer(r"\*+", norm) if m.end() - m.start() == len(n)]
        else:
            i = 0
            while True:
                j = low.find(n, i)
                if j < 0:
                    break
                starts.append(j)
                i = j + 1
        if len(starts) <= nth:
            raise SystemExit(
                f"{stem}.txt: {needle!r} chỉ có {len(starts)} lần xuất hiện, cần index {nth}"
            )
        s0 = starts[nth] + pre_len
        s1 = s0 + (core_len if core_len is not None else len(n))
        a, b = to_raw_span(imap, len(raw), s0, s1)
        # invariant: span trên file gốc phải trỏ đúng cụm đã annotate
        want = normalize(needle[len(pre):len(needle) - len(post)] if core_len is not None else needle)[0].lower()
        got = normalize(raw[a:b])[0].lower()
        if got != want:
            raise SystemExit(f"{stem}.txt: span [{a},{b}] ra {got!r}, cần {want!r}")
        out.append(
            {
                "text": raw[a:b],
                "position": [a, b],
                "type": typ,
                "assertions": asserts,
                "candidates": cands,
            }
        )
    out.sort(key=lambda e: e["position"][0])
    return out


def main() -> None:
    outdir = ROOT / "data" / "gt"
    outdir.mkdir(parents=True, exist_ok=True)
    total = 0
    for stem, ann in GT.items():
        ents = resolve(stem, ann)
        # không cho phép hai entity trùng span
        spans = [tuple(e["position"]) for e in ents]
        dup = {s for s in spans if spans.count(s) > 1}
        if dup:
            raise SystemExit(f"{stem}.txt: span trùng {dup}")
        (outdir / f"{stem}.json").write_text(
            json.dumps(ents, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        total += len(ents)
        kinds: dict[str, int] = {}
        for e in ents:
            kinds[e["type"]] = kinds.get(e["type"], 0) + 1
        na = sum(1 for e in ents if e["assertions"])
        nc = sum(1 for e in ents if e["candidates"])
        print(f"  {stem}.json  {len(ents):3d} entity  assert {na:2d}  cand {nc:2d}  {kinds}")
    print(f"\n{len(GT)} file, {total} entity -> {outdir}")


if __name__ == "__main__":
    main()
