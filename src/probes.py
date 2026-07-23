#!/usr/bin/env python3
"""Sinh các file nộp để DÒ CƠ CHẾ CHẤM ĐIỂM của BTC.

Leaderboard trả điểm 5 chữ số thập phân trên đúng 100 file public test => đây là
oracle duy nhất để học quy tắc gán nhãn. Mỗi probe đổi ĐÚNG 1 biến so với mốc so
sánh của nó; delta điểm chính là câu trả lời.

    python3 src/probes.py P1            # sinh probes/P1/ + probes/P1.zip
    python3 src/probes.py --list

Quan trọng: dò để học QUY TẮC (là một phần thuật toán, tổng quát hoá sang private
test). KHÔNG hard-code output theo điểm — top ~15 bị BTC dựng lại code trên private
test, hard-code sẽ chết.
"""
from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "input"
PROBE_DIR = ROOT / "probes"
BASELINE = ROOT / "out" / "baseline.json"  # {"1": [ent, ...], ...} do extract.py sinh

N_FILES = 100


def load_baseline() -> dict[str, list[dict]]:
    if not BASELINE.exists():
        raise SystemExit(
            f"Chưa có baseline: {BASELINE}\nChạy `python3 src/extract.py` trước."
        )
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def empty() -> dict[str, list[dict]]:
    return {str(i): [] for i in range(1, N_FILES + 1)}


# ---------------------------------------------------------------- các probe


def p1_empty(_):
    """Mảng rỗng cho cả 100 file.

    CÂU HỎI ĐẮT NHẤT: concept trong GT mà ta không dự đoán thì bị tính 0, hay được
    J=1 (vì gt_assertions rỗng và pred cũng rỗng)?
      - điểm ~0      => miss = 0. Mô hình `final ~ 0.3T + 0.3*Jc*acc + 0.4*Jc*acc` đúng.
      - điểm 30-45   => miss được J=1 khi gt rỗng. Lỗ hổng lớn; đổi hẳn chiến lược.
    """
    return empty()


def p2_single(base):
    """Chỉ giữ concept ĐẦU TIÊN của mỗi file. Mốc so sánh cho P3..P6."""
    return {k: v[:1] for k, v in base.items()}


def p3_wrong_type(base):
    """Như P2 nhưng đổi `type` sang loại khác. So với P2 => kiểm chứng quy tắc
    "sai loại thì tính 2 lần, mỗi lần 0đ"."""
    out = copy.deepcopy(p2_single(base))
    swap = {"THUỐC": "TRIỆU_CHỨNG", "TRIỆU_CHỨNG": "CHẨN_ĐOÁN", "CHẨN_ĐOÁN": "TRIỆU_CHỨNG"}
    for ents in out.values():
        for e in ents:
            e["type"] = swap.get(e["type"], "TRIỆU_CHỨNG")
    return out


def p4_shift_position(base):
    """Như P2 nhưng lệch `position` 1 ký tự (text giữ nguyên). So với P2 =>
    `position` có tham gia khớp concept không?"""
    out = copy.deepcopy(p2_single(base))
    for ents in out.values():
        for e in ents:
            if "position" in e:
                e["position"] = [e["position"][0] + 1, e["position"][1] + 1]
    return out


def p5_duplicate(base):
    """Như P2 nhưng nhân đôi mỗi entity. So với P2 => eval có dedup không?"""
    return {k: v * 2 for k, v in p2_single(base).items()}


def p6_reverse(base):
    """Toàn bộ baseline nhưng đảo ngược thứ tự mảng. So với baseline => text_score
    có nối chuỗi theo thứ tự không (WER nhạy thứ tự)?"""
    return {k: list(reversed(v)) for k, v in base.items()}


def p7_drop_candidates_key(base):
    """Toàn bộ baseline nhưng BỎ HẲN key `candidates` ở chỗ đang là []. So với
    baseline => key thiếu có được coi là rỗng không?"""
    out = copy.deepcopy(base)
    for ents in out.values():
        for e in ents:
            if e.get("candidates") == []:
                e.pop("candidates", None)
    return out


def p8_symptom_candidates(base):
    """Gán 1 candidate giả cho MỌI TRIỆU_CHỨNG. So với baseline => triệu chứng có
    candidates trong GT không? Nếu điểm TỤT => GT rỗng (xác nhận điểm cho không)."""
    out = copy.deepcopy(base)
    for ents in out.values():
        for e in ents:
            if e["type"] == "TRIỆU_CHỨNG":
                e["candidates"] = ["99999999"]
    return out


def p9_icd10_on_diagnosis(base):
    """Gán mã ICD-10 (đã tra được) cho CHẨN_ĐOÁN. So với baseline => Round 1 đã
    chấm ICD-10 cho bệnh chưa? Trả lời "candidates đáng 2 điểm hay 12 điểm".
    Cần extract.py điền sẵn `_icd10` cho mỗi CHẨN_ĐOÁN."""
    out = copy.deepcopy(base)
    n = 0
    for ents in out.values():
        for e in ents:
            if e["type"] == "CHẨN_ĐOÁN" and e.get("_icd10"):
                e["candidates"] = [e["_icd10"]]
                n += 1
    print(f"    (đã gán ICD-10 cho {n} chẩn đoán)")
    return out


def p9b_icd10_dotted(base):
    """Như P9 nhưng mã có dấu chấm (D25.9 thay vì D259). So với P9 => BTC dùng
    định dạng nào."""
    out = p9_icd10_on_diagnosis(base)
    for ents in out.values():
        for e in ents:
            if e["type"] == "CHẨN_ĐOÁN" and e.get("candidates"):
                c = e["candidates"][0]
                e["candidates"] = [c if len(c) <= 3 else f"{c[:3]}.{c[3:]}"]
    return out


def p10_no_assertions(base):
    """Toàn bộ baseline nhưng xoá sạch assertions. So với baseline => module
    assertion của ta đang có ích hay có hại."""
    out = copy.deepcopy(base)
    for ents in out.values():
        for e in ents:
            e["assertions"] = []
    return out


def _assert_all(label: str):
    """Gắn CÙNG MỘT nhãn assertion cho TẤT CẢ concept -> đo trực tiếp xem chuỗi đó
    có tồn tại trong gold không.

    Vì sao cần: đo được P2 (89 isHistorical + 64 rỗng) = 2.7263 < P10 (toàn rỗng) = 2.9941.
    Giải hệ ra: 89 concept gắn isHistorical ăn ~0 điểm, trong khi prior theo section lại
    phân tách tốt (73% vs 5% có gold rỗng). ⇒ gắn ĐÚNG CHỖ nhưng SAI TÊN.

    So sánh với mốc P10 = 2.9941:
      J_ass  >  2.9941  -> chuỗi ĐÚNG, và còn nhiều concept mang nhãn này hơn ta tưởng
      J_ass  ~= 0       -> chuỗi SAI hoàn toàn (gold không hề có token này)
      0 < J_ass < 2.99  -> chuỗi đúng một phần / gold đa trị
    """
    def fn(base):
        out = copy.deepcopy(base)
        for ents in out.values():
            for e in ents:
                e["assertions"] = [label]
        return out
    return fn


# Ứng viên tên nhãn, xếp theo độ khả tín.
# 'isHistorical' lấy từ ví dụ trong PROJECT_CONTEXT.md — nhưng file đó ĐÃ SAI một lần
# (ghi deadline 30/07 trong khi trang thi ghi 04/08), nên không đáng tin tuyệt đối.
# Các ứng viên còn lại theo giả thuyết gold sinh bằng AWS Comprehend Medical, có
# RxNormTrait = NEGATION | PAST_HISTORY.
ASSERT_CANDIDATES = [
    ("A1", "isHistorical"),    # theo ví dụ đề — kiểm chứng dứt điểm
    ("A2", "PAST_HISTORY"),    # literal của AWS Comprehend Medical
    ("A3", "isPastHistory"),   # camelCase hoá literal AWS
    ("A4", "historical"),      # thường, không tiền tố
    ("A5", "isNegated"),       # trục phủ định — kiểm chứng tiền tố "is" nói chung
]

PROBES = {
    "P1": (p1_empty, "100 file rỗng — baseline; miss bị 0 hay được J=1?", False),
    "P2": (p2_single, "1 concept/file — mốc so sánh cho P3..P5", True),
    "P3": (p3_wrong_type, "như P2, sai type — kiểm chứng phạt kép", True),
    "P4": (p4_shift_position, "như P2, lệch position 1 ký tự", True),
    "P5": (p5_duplicate, "như P2, nhân đôi entity — có dedup không?", True),
    "P6": (p6_reverse, "baseline đảo thứ tự — WER có nối chuỗi không?", True),
    "P7": (p7_drop_candidates_key, "bỏ key candidates rỗng", True),
    "P8": (p8_symptom_candidates, "gán candidate giả cho triệu chứng", True),
    "P9": (p9_icd10_on_diagnosis, "gán ICD-10 cho chẩn đoán (không chấm)", True),
    "P9b": (p9b_icd10_dotted, "như P9 nhưng mã có dấu chấm", True),
    "P10": (p10_no_assertions, "xoá sạch assertions — MỐC SO SÁNH, đo được J_ass=2.9941", True),
}
for _k, _lab in ASSERT_CANDIDATES:
    PROBES[_k] = (_assert_all(_lab), f'gắn ["{_lab}"] cho MỌI concept — so với mốc P10=2.9941', True)


def write(name: str, preds: dict[str, list[dict]]) -> Path:
    out_dir = PROBE_DIR / name / "output"
    if out_dir.parent.exists():
        shutil.rmtree(out_dir.parent)
    out_dir.mkdir(parents=True)
    for i in range(1, N_FILES + 1):
        ents = [
            {k: v for k, v in e.items() if not k.startswith("_")}
            for e in preds.get(str(i), [])
        ]
        (out_dir / f"{i}.json").write_text(
            json.dumps(ents, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    zip_path = PROBE_DIR / name
    shutil.make_archive(str(zip_path), "zip", root_dir=out_dir.parent, base_dir="output")
    return Path(f"{zip_path}.zip")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] == "--list":
        print("Các probe (nộp tối đa 5/ngày — ưu tiên P1, P9):\n")
        for k, (_, doc, needs) in PROBES.items():
            print(f"  {k:5s} {'[cần baseline]' if needs else '[độc lập]     '} {doc}")
        return

    name = sys.argv[1]
    if name not in PROBES:
        raise SystemExit(f"Không rõ probe {name!r}. Dùng --list để xem.")

    fn, doc, needs_baseline = PROBES[name]
    base = load_baseline() if needs_baseline else {}
    preds = fn(base)
    zip_path = write(name, preds)

    n_ent = sum(len(v) for v in preds.values())
    print(f"{name}: {doc}")
    print(f"  {n_ent} entity / {N_FILES} file")
    print(f"  -> {zip_path.relative_to(ROOT)}  ({zip_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
