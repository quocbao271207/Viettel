"""Tách 100 file input thành block, gom block trùng lặp.

Tập test được BTC sinh bằng cách ghép 2-4 block từ một pool nhỏ (xem PLAN.md §3.1).
Module này đảo ngược quá trình đó: tìm tập block độc nhất và map ngược
(block_id -> các vị trí nó xuất hiện trong 100 file).

Nhãn của một block bất biến qua các file, chỉ khác `position`. Nên chỉ cần
annotate tập block độc nhất, rồi chiếu ngược ra 100 file.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "input"
OUT_DIR = ROOT / "data" / "blocks"

# Ranh giới block: dòng trống, hoặc header section đánh số ("1. Tiền sử bệnh"),
# hoặc chuyển thể loại QA <-> EHR.
RE_NUM_HEADER = re.compile(r"^\s*\d+\s*[.)/]\s*\S")
RE_GENRE_MARK = re.compile(
    r"^\s*(Câu hỏi từ người dùng|Câu trả lời của bác sĩ|Trả lời)\s*[:.]?\s*$",
    re.IGNORECASE,
)

MIN_BLOCK_CHARS = 40  # block ngắn hơn thì gộp vào block trước


def norm_for_hash(text: str) -> str:
    """Chuẩn hóa để so trùng: NFC, bỏ dấu câu lẻ, gộp khoảng trắng, lower.

    Chỉ dùng cho việc so trùng — KHÔNG dùng để tính position.
    """
    t = unicodedata.normalize("NFC", text).lower()
    t = re.sub(r"[^\w\s]+", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


@dataclass
class Span:
    """Một lần xuất hiện của block trong một file."""

    file: str
    start: int
    end: int


@dataclass
class Block:
    block_id: int
    text: str  # nguyên văn của lần xuất hiện đầu tiên
    norm: str
    n_chars: int
    spans: list[Span]

    @property
    def n_occurrences(self) -> int:
        return len(self.spans)


def split_blocks(text: str) -> list[tuple[int, int]]:
    """Trả về list (start, end) offset ký tự của từng block trong text.

    Offset tính trên text gốc, không chuẩn hóa — để position khớp yêu cầu đề.
    """
    lines: list[tuple[int, int]] = []  # (start, end) của từng dòng
    pos = 0
    for line in text.splitlines(keepends=True):
        lines.append((pos, pos + len(line)))
        pos += len(line)

    # Xác định dòng nào mở đầu một block mới
    starts: list[int] = []
    prev_blank = True
    for i, (s, e) in enumerate(lines):
        raw = text[s:e]
        stripped = raw.strip()
        is_blank = not stripped
        if is_blank:
            prev_blank = True
            continue
        if prev_blank or RE_NUM_HEADER.match(raw) or RE_GENRE_MARK.match(raw):
            starts.append(i)
        prev_blank = False

    if not starts:
        return [(0, len(text))] if text.strip() else []

    # Ghép các dòng thành block theo mốc starts
    blocks: list[tuple[int, int]] = []
    for k, li in enumerate(starts):
        lo = lines[li][0]
        hi = lines[starts[k + 1]][0] if k + 1 < len(starts) else len(text)
        blocks.append((lo, hi))

    # Gộp block quá ngắn vào block trước
    merged: list[tuple[int, int]] = []
    for lo, hi in blocks:
        if merged and len(text[lo:hi].strip()) < MIN_BLOCK_CHARS:
            merged[-1] = (merged[-1][0], hi)
        else:
            merged.append((lo, hi))

    # Cắt phần trắng ở hai đầu để position sát nội dung thật
    out: list[tuple[int, int]] = []
    for lo, hi in merged:
        seg = text[lo:hi]
        l_pad = len(seg) - len(seg.lstrip())
        r_pad = len(seg) - len(seg.rstrip())
        lo2, hi2 = lo + l_pad, hi - r_pad
        if hi2 > lo2:
            out.append((lo2, hi2))
    return out


def build(input_dir: Path = INPUT_DIR) -> tuple[list[Block], dict]:
    files = sorted(input_dir.glob("*.txt"), key=lambda p: int(p.stem))
    by_norm: dict[str, Block] = {}
    order: list[str] = []
    stats = {"n_files": len(files), "n_block_instances": 0, "n_chars_total": 0}

    for path in files:
        text = path.read_text(encoding="utf-8")
        stats["n_chars_total"] += len(text)
        for lo, hi in split_blocks(text):
            raw = text[lo:hi]
            key = norm_for_hash(raw)
            if not key:
                continue
            stats["n_block_instances"] += 1
            span = Span(file=path.name, start=lo, end=hi)
            if key in by_norm:
                by_norm[key].spans.append(span)
            else:
                by_norm[key] = Block(
                    block_id=-1, text=raw, norm=key, n_chars=len(raw), spans=[span]
                )
                order.append(key)

    # Gán id theo thứ tự giảm dần số lần xuất hiện (block hay gặp nhất = id nhỏ)
    blocks = [by_norm[k] for k in order]
    blocks.sort(key=lambda b: (-b.n_occurrences, -b.n_chars))
    for i, b in enumerate(blocks):
        b.block_id = i

    stats["n_unique_blocks"] = len(blocks)
    stats["n_repeated_blocks"] = sum(1 for b in blocks if b.n_occurrences > 1)
    stats["n_chars_unique"] = sum(b.n_chars for b in blocks)
    stats["dedup_ratio"] = round(
        stats["n_chars_unique"] / max(1, stats["n_chars_total"]), 4
    )
    return blocks, stats


def save(blocks: list[Block], stats: dict, out_dir: Path = OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "block_id": b.block_id,
            "n_chars": b.n_chars,
            "n_occurrences": b.n_occurrences,
            "text": b.text,
            "spans": [asdict(s) for s in b.spans],
        }
        for b in blocks
    ]
    (out_dir / "blocks.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (out_dir / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    # Index ngược: file -> các block nó chứa, theo thứ tự xuất hiện
    per_file: dict[str, list[dict]] = defaultdict(list)
    for b in blocks:
        for s in b.spans:
            per_file[s.file].append(
                {"block_id": b.block_id, "start": s.start, "end": s.end}
            )
    for f in per_file:
        per_file[f].sort(key=lambda d: d["start"])
    (out_dir / "file_to_blocks.json").write_text(
        json.dumps(per_file, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def verify(blocks: list[Block], input_dir: Path = INPUT_DIR) -> list[str]:
    """Kiểm tra offset: text[start:end] phải khớp nguyên văn block.

    Đây là bất biến quan trọng nhất — position sai thì mất điểm toàn bộ.
    """
    cache = {
        p.name: p.read_text(encoding="utf-8") for p in input_dir.glob("*.txt")
    }
    errors: list[str] = []
    for b in blocks:
        for s in b.spans:
            got = cache[s.file][s.start : s.end]
            if norm_for_hash(got) != b.norm:
                errors.append(
                    f"block {b.block_id} @ {s.file}[{s.start}:{s.end}] lệch nội dung"
                )
    return errors


if __name__ == "__main__":
    blocks, stats = build()
    errors = verify(blocks)
    save(blocks, stats)

    print("=== dedupe block ===")
    for k, v in stats.items():
        print(f"  {k:22s} {v}")
    print(f"  offset errors          {len(errors)}")
    for e in errors[:5]:
        print("   !", e)

    print("\n=== top 15 block xuất hiện nhiều nhất ===")
    for b in blocks[:15]:
        head = re.sub(r"\s+", " ", b.text)[:64]
        print(f"  #{b.block_id:3d} ×{b.n_occurrences:2d} {b.n_chars:5d}c  {head}")
