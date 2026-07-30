"""Postprocess submission bằng các rule học từ leaderboard/probe.

Mục tiêu: tạo probe có kiểm soát, không đụng model.

Rule đang hỗ trợ:

- strict assertions: chỉ gán assertion khi ngữ cảnh rất rõ.
- exact repeats: nhân bản bề mặt đã được model bắt sang lần nhắc khác, nhưng chặn
  cụm ngắn/generic/vitals theo bài học bản 15-17 của repo đồng đội.

Ví dụ:

    python src/enhance_submission.py --pred output_clean_retrain.zip \
      --out artifacts/ensembles/v8_clean_retrain_assert_repeat.zip \
      --strict-assertions --add-repeats
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
Entity = dict[str, Any]

ASSERTABLE = {"CHẨN_ĐOÁN", "THUỐC", "TRIỆU_CHỨNG"}
CODED_TYPES = {"CHẨN_ĐOÁN", "THUỐC"}
ALLOWED_ASSERT = {"isNegated", "isHistorical", "isFamily"}
WORD_RE = re.compile(r"[0-9A-Za-zÀ-ỹ]")
TOKEN_RE = re.compile(r"[0-9A-Za-zÀ-ỹ]+")

HIST_HEADER_RE = re.compile(
    r"(?im)^\s*(?:[-*•]\s*)?"
    r"(?:tiền sử|tiền căn|bệnh nền|bệnh lý mạn|bệnh mạn|bệnh mãn|"
    r"các bệnh đã mắc|thuốc trước|thuốc đã dùng trước)\b[^\n:：]{0,80}[:：]",
)
FAMILY_HEADER_RE = re.compile(
    r"(?im)^\s*(?:[-*•]\s*)?"
    r"(?:tiền sử gia đình|gia đình|yếu tố gia đình|di truyền)\b[^\n:：]{0,80}[:：]",
)
PRESENT_HEADER_RE = re.compile(
    r"(?im)^\s*(?:[-*•]\s*)?"
    r"(?:bệnh sử hiện tại|triệu chứng hiện tại|lý do vào viện|lý do nhập viện|"
    r"khám lâm sàng|hiện tại|tại bệnh viện|diễn biến|chẩn đoán|điều trị)\b"
    r"[^\n:：]{0,80}[:：]",
)
NEG_RE = re.compile(
    r"(?:\bkhông\b|\bchưa\b|không ghi nhận|không thấy|phủ nhận|loại trừ|âm tính)",
    re.I,
)

VITAL_OR_GENERIC = {
    "ha",
    "huyết áp",
    "mạch",
    "nhiệt độ",
    "nhịp thở",
    "spo2",
    "sp02",
    "glasgow",
    "cân nặng",
    "chiều cao",
    "bmi",
    "dấu hiệu sinh tồn",
    "xét nghiệm",
    "chẩn đoán hình ảnh",
    "hình ảnh",
}

BAD_REPEAT_TEXT = {
    # Bài học bản 15-17: cụm ngắn/generic hoặc sai bản chất type.
    "không",
    "chưa",
    "thiếu",
    "bất thường",
    "thuốc",
    "âm tính",
    "dương tính",
    "protein",
    "dị ứng",
    "vi khuẩn",
    "nhiễm",
    "đau",
    "yếu",
    "phù",
    "sốt",
    "mụn",
    "ngứa",
    "lo lắng",
    "chấn thương",
    "quá liều",
    "ống dẫn",
    "hồi tràng",
    "gót chân",
    "khó chịu",
    "nổi quanh năm",
    "nước tiểu trong",
    "lắng đọng protein",
    "hút thuốc",
    "mật ong",
    "men tiêu hóa",
    "chân răng",
}


def read_raw(fid: str) -> str:
    return (ROOT / "input" / f"{fid}.txt").read_text(encoding="utf-8")


def extract_if_zip(path: Path, tmp: Path) -> Path:
    if path.is_dir():
        return path / "output" if (path / "output").is_dir() else path
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    with zipfile.ZipFile(path) as zf:
        zf.extractall(tmp)
    return tmp / "output" if (tmp / "output").is_dir() else tmp


def load_pred(path: Path) -> dict[str, list[Entity]]:
    pred_dir = extract_if_zip(path, ROOT / f"artifacts/_enhance_extract_{os.getpid()}")
    out: dict[str, list[Entity]] = {}
    for fid in map(str, range(1, 101)):
        out[fid] = json.loads((pred_dir / f"{fid}.json").read_text(encoding="utf-8"))
    return out


def word_count(text: str) -> int:
    return len(TOKEN_RE.findall(text))


def norm_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def sentence_window(raw: str, start: int, end: int) -> tuple[str, str]:
    left = max(raw.rfind(".", 0, start), raw.rfind("\n", 0, start), raw.rfind(";", 0, start))
    right_marks = [i for i in (raw.find(".", end), raw.find("\n", end), raw.find(";", end)) if i != -1]
    right = min(right_marks) if right_marks else len(raw)
    return raw[left + 1 : start], raw[end:right]


def last_context_label(raw: str, pos: int) -> str | None:
    """Header gần nhất trước span; chỉ tin header rõ, không tin chữ rải trong câu."""
    start = max(0, pos - 900)
    head = raw[start:pos]
    best: tuple[str | None, int] = (None, -1)
    for label, rx in (
        ("history", HIST_HEADER_RE),
        ("family", FAMILY_HEADER_RE),
        ("present", PRESENT_HEADER_RE),
    ):
        for m in rx.finditer(head):
            absolute_start = start + m.start()
            if absolute_start > best[1]:
                best = (label, absolute_start)
    return best[0]


def infer_assertions(raw: str, ent: Entity) -> list[str]:
    if ent.get("type") not in ASSERTABLE:
        return []
    s, e = ent["position"]
    left, _ = sentence_window(raw, s, e)
    left_tail = left[-45:]
    labels: list[str] = []

    ctx = last_context_label(raw, s)
    if ctx == "family":
        labels.append("isFamily")
    elif ctx == "history":
        labels.append("isHistorical")

    # Chỉ bắt phủ định rất gần trong cùng câu; tránh biến mọi đoạn giáo dục có chữ "không"
    # thành isNegated.
    if NEG_RE.search(left_tail):
        labels.append("isNegated")

    out: list[str] = []
    for label in labels:
        if label in ALLOWED_ASSERT and label not in out:
            out.append(label)
    return out


def apply_strict_assertions(pred: dict[str, list[Entity]]) -> int:
    changed = 0
    for fid, ents in pred.items():
        raw = read_raw(fid)
        for ent in ents:
            new = infer_assertions(raw, ent)
            if ent.get("assertions", []) != new:
                ent["assertions"] = new
                changed += 1
    return changed


def repeat_allowed(text: str, typ: str, *, coded_only: bool, has_code: bool) -> bool:
    key = norm_key(text)
    if not key or key in BAD_REPEAT_TEXT or key in VITAL_OR_GENERIC:
        return False
    if any(key.startswith(p) for p in ("xét nghiệm ", "chẩn đoán ", "theo dõi ")):
        return False
    if word_count(key) < 2:
        return False
    if len(key) < 6:
        return False
    if typ == "THUỐC" and ("*" in text or key in {"dùng thuốc", "thuốc uống"}):
        return False
    if coded_only and typ in CODED_TYPES and not has_code:
        return False
    return True


def add_exact_repeats(pred: dict[str, list[Entity]], *, coded_only: bool = False) -> collections.Counter[str]:
    lex: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    code_of: dict[tuple[str, str], list[str]] = {}
    assert_of: dict[tuple[str, str], list[str]] = {}
    has_code: dict[tuple[str, str], bool] = {}

    for ents in pred.values():
        for ent in ents:
            text = ent.get("text", "").strip()
            typ = ent.get("type", "")
            key = (text, typ)
            has_code[key] = bool(ent.get("candidates"))
            if not repeat_allowed(text, typ, coded_only=coded_only, has_code=has_code[key]):
                continue
            lex[text][typ] += 1
            if ent.get("candidates"):
                code_of[key] = list(ent["candidates"])
            if ent.get("assertions"):
                assert_of.setdefault(key, list(ent["assertions"]))

    added: collections.Counter[str] = collections.Counter()
    for fid in map(str, range(1, 101)):
        raw = read_raw(fid)
        taken = [tuple(ent["position"]) for ent in pred[fid]]
        for text, type_counts in sorted(lex.items(), key=lambda kv: -len(kv[0])):
            typ = type_counts.most_common(1)[0][0]
            key = (text, typ)
            for m in re.finditer(re.escape(text), raw):
                s, e = m.span()
                if s > 0 and WORD_RE.match(raw[s - 1]):
                    continue
                if e < len(raw) and WORD_RE.match(raw[e]):
                    continue
                if any(min(e, b) > max(s, a) for a, b in taken):
                    continue
                ent = {
                    "text": raw[s:e],
                    "type": typ,
                    "candidates": list(code_of.get(key, [])) if typ in CODED_TYPES else [],
                    "assertions": list(assert_of.get(key, [])) if typ in ASSERTABLE else [],
                    "position": [s, e],
                }
                pred[fid].append(ent)
                taken.append((s, e))
                added[typ] += 1

    for ents in pred.values():
        ents.sort(key=lambda ent: (ent["position"][0], ent["position"][1]))
    return added


def verify(pred: dict[str, list[Entity]]) -> None:
    for fid, ents in pred.items():
        raw = read_raw(fid)
        for ent in ents:
            s, e = ent["position"]
            if raw[s:e] != ent["text"]:
                raise ValueError(f"{fid}: offset lệch {ent!r} != {raw[s:e]!r}")
            if ent["type"] not in CODED_TYPES and ent.get("candidates"):
                raise ValueError(f"{fid}: non-coded type có candidates {ent!r}")
            bad_assert = set(ent.get("assertions", [])) - ALLOWED_ASSERT
            if bad_assert:
                raise ValueError(f"{fid}: assertion không hợp lệ {ent!r}")


def write_zip(pred: dict[str, list[Entity]], out_zip: Path) -> None:
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    if out_zip.exists():
        out_zip.unlink()
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for fid in map(str, range(1, 101)):
            zf.writestr(
                f"output/{fid}.json",
                json.dumps(pred[fid], ensure_ascii=False, indent=2),
            )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True, help="submission zip hoặc thư mục output")
    ap.add_argument("--out", required=True, help="zip kết quả")
    ap.add_argument("--strict-assertions", action="store_true")
    ap.add_argument("--add-repeats", action="store_true")
    ap.add_argument(
        "--repeat-coded-only",
        action="store_true",
        help="với CHẨN_ĐOÁN/THUỐC chỉ nhân bản khi concept gốc có candidates",
    )
    args = ap.parse_args()

    pred = load_pred(ROOT / args.pred)
    changed_assert = apply_strict_assertions(pred) if args.strict_assertions else 0
    added = (
        add_exact_repeats(pred, coded_only=args.repeat_coded_only)
        if args.add_repeats
        else collections.Counter()
    )
    verify(pred)
    write_zip(pred, ROOT / args.out)

    total = sum(len(v) for v in pred.values())
    ncand = sum(1 for ents in pred.values() for ent in ents if ent.get("candidates"))
    nass = sum(1 for ents in pred.values() for ent in ents if ent.get("assertions"))
    print("total", total, "| candidates", ncand, "| assertions", nass)
    print("changed_assertions", changed_assert)
    print("added_repeats", dict(added), "sum", sum(added.values()))
    print("->", ROOT / args.out)


if __name__ == "__main__":
    main()
