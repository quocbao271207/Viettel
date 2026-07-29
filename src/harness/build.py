#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LÕI HARNESS — phiếu voter thô  ->  bản nộp đã kiểm định.

    # đọc mọi voter trong dev/votes_v2/, dựng bản consensus k>=2
    python3 -m src.harness.build --k 2 --out out/candidates/v2_k2.zip

    # xem thống kê định vị của từng voter, không dựng zip
    python3 -m src.harness.build --report

Luồng TẤT ĐỊNH, một chiều, không có bước sửa tay:
    phiếu thô -> ĐỊNH VỊ (locate) -> LỌC CẤM (spec) -> GỘP PHIẾU -> GÁN MÃ -> CỔNG CỨNG -> zip

Ngưỡng `k` là NÚM VẶN, không phải giả định: cùng một lần chạy voter sinh ra được
k=1/2/3 để leaderboard tự nói điểm chính xác/độ phủ nằm ở đâu.
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.harness import locate as loc      # noqa: E402
from src.harness import spec, validate     # noqa: E402

VOTES = ROOT / "dev/votes_v2"
BASE_ZIP = ROOT / "out/submitted/14_repeat_36.4914.zip"


def norm(s: str) -> str:
    return unicodedata.normalize("NFC", s or "").strip().lower()


# ------------------------------------------------------------------ bản đồ mã

def code_map_from_base() -> dict[tuple[str, str], list[str]]:
    """(text chuẩn hoá, type) -> candidates, lấy từ bản 14.

    Đây là bộ mã ĐÃ QUA LEADERBOARD: bản 10 sửa 9 mã ăn +0.20, bản 13 audit toàn bộ 366 cặp.
    Dùng lại nguyên vẹn để khi thử nghiệm NER thì trục J_cand không bị nhiễu.
    """
    base = validate.load_zip(BASE_ZIP)
    m: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for v in base.values():
        for e in v:
            if e["type"] in spec.CODED_TYPES and e.get("candidates"):
                m[(norm(e["text"]), e["type"])][tuple(e["candidates"])] += 1
    return {k: list(c.most_common(1)[0][0]) for k, c in m.items()}


# ------------------------------------------------------------------ định vị 1 voter

def resolve_voter(votes: dict[str, list[dict]], apply_ban: bool = True) -> tuple[dict, Counter]:
    """Phiếu thô -> {fid: [concept đã có position]}, kèm thống kê lý do loại."""
    out: dict[str, list[dict]] = {str(i): [] for i in range(1, 101)}
    stats: Counter = Counter()
    for fid, items in votes.items():
        if fid not in out or not isinstance(items, list):
            stats["file lạ"] += len(items or [])
            continue
        raw = validate.read_raw(int(fid))
        # Gom theo (text, type, before, after): voter báo N lần = có N lần nhắc.
        # Bắt buộc phải gom, vì đoạn văn lặp làm 15 ký tự ngữ cảnh mất khả năng phân biệt.
        groups: dict[tuple, list[dict]] = defaultdict(list)
        for e in items:
            if not isinstance(e, dict) or "text" not in e:
                stats["mục hỏng"] += 1
                continue
            t = (e.get("type") or "").strip()
            if t not in spec.TYPES:
                stats[f"type lạ: {t[:20]}"] += 1
                continue
            if apply_ban:
                why = spec.is_banned(e["text"], t)
                if why:
                    stats[f"CẤM: {why}"] += 1
                    continue
            groups[(e["text"], t, e.get("before", ""), e.get("after", ""))].append(e)

        seen: set[tuple[int, int, str]] = set()
        for (text, t, before, after), reqs in groups.items():
            spans, mode = loc.locate_group(raw, text, before, after, len(reqs))
            if not spans:
                stats[f"loại: {mode}"] += len(reqs)
                continue
            if len(spans) < len(reqs):
                stats["thừa phiếu so với số lần xuất hiện"] += len(reqs) - len(spans)
            for e, (s, t_end, mmode) in zip(reqs, spans):
                key = (s, t_end, t)
                if key in seen:        # cùng voter trả trùng -> giữ 1
                    stats["trùng trong cùng voter"] += 1
                    continue
                seen.add(key)
                asserts = [a for a in (e.get("assertions") or []) if a in spec.ASSERTIONS]
                out[fid].append({"text": raw[s:t_end], "type": t,
                                 "assertions": sorted(set(asserts)),
                                 "position": [s, t_end], "_mode": mmode})
                stats["NHẬN"] += 1
                if mode == "ordinal":
                    stats["  (trong đó: gán theo thứ tự vì ngữ cảnh lặp)"] += 1
    return out, stats


# ------------------------------------------------------------------ gộp phiếu

def merge(resolved: dict[str, dict], k: int) -> dict[str, list[dict]]:
    """Gộp nhiều voter. Giữ concept có >= k phiếu. Assertion theo đa số phiếu."""
    bucket: dict[str, dict[tuple, dict]] = {str(i): {} for i in range(1, 101)}
    for vname, per_file in resolved.items():
        for fid, items in per_file.items():
            for e in items:
                key = (e["position"][0], e["position"][1], e["type"])
                slot = bucket[fid].setdefault(
                    key, {"text": e["text"], "type": e["type"],
                          "voters": set(), "asserts": Counter()})
                slot["voters"].add(vname)
                slot["asserts"][tuple(e["assertions"])] += 1
    out: dict[str, list[dict]] = {}
    for fid in sorted(bucket, key=int):
        rows = []
        for (s, t, ty), slot in bucket[fid].items():
            if len(slot["voters"]) < k:
                continue
            rows.append({"text": slot["text"], "type": ty,
                         "candidates": [], "assertions": list(slot["asserts"].most_common(1)[0][0]),
                         "position": [s, t], "_votes": len(slot["voters"])})
        rows.sort(key=lambda r: (r["position"][0], r["position"][1]))
        out[fid] = rows
    return out


def assign_codes(preds: dict[str, list[dict]], cmap: dict) -> dict[str, list[dict]]:
    for v in preds.values():
        for e in v:
            e["candidates"] = (list(cmap.get((norm(e["text"]), e["type"]), []))
                               if e["type"] in spec.CODED_TYPES else [])
    return preds


def strip_meta(preds: dict[str, list[dict]]) -> dict[str, list[dict]]:
    return {fid: [{kk: e[kk] for kk in ("text", "type", "candidates", "assertions", "position")}
                  for e in v] for fid, v in preds.items()}


def write_zip(preds: dict[str, list[dict]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for fid in sorted(preds, key=int):
            z.writestr(f"output/{fid}.json",
                       json.dumps(preds[fid], ensure_ascii=False, indent=1))


# ------------------------------------------------------------------ CLI

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=2, help="số phiếu tối thiểu để giữ concept")
    ap.add_argument("--voters", default="", help="lọc voter, ngăn bởi dấu phẩy")
    ap.add_argument("--out", default="", help="đường dẫn zip; bỏ trống = chỉ báo cáo")
    ap.add_argument("--report", action="store_true", help="in thống kê định vị rồi thoát")
    ap.add_argument("--no-ban", action="store_true", help="tắt danh sách cấm (chỉ để chẩn đoán)")
    args = ap.parse_args()

    files = sorted(VOTES.glob("*.json"))
    if args.voters:
        want = {x.strip() for x in args.voters.split(",")}
        files = [f for f in files if f.stem in want]
    if not files:
        raise SystemExit(f"Không có phiếu nào trong {VOTES} — chạy voter trước.")

    resolved: dict[str, dict] = {}
    for f in files:
        votes = json.loads(f.read_text(encoding="utf-8"))
        r, st = resolve_voter(votes, apply_ban=not args.no_ban)
        resolved[f.stem] = r
        raw_n = sum(len(v) for v in votes.values() if isinstance(v, list))
        print(f"[{f.stem}] thô {raw_n} -> nhận {st['NHẬN']} "
              f"({st['NHẬN']/max(raw_n,1)*100:.0f}%)")
        for reason, n in st.most_common():
            if reason != "NHẬN":
                print(f"      {n:5d}  {reason}")

    if args.report:
        return

    cmap = code_map_from_base()
    for k in ([args.k] if args.out else (1, 2, 3)):
        preds = assign_codes(merge(resolved, k), cmap)
        tot = sum(len(v) for v in preds.values())
        coded = sum(1 for v in preds.values() for e in v
                    if e["type"] in spec.CODED_TYPES and e["candidates"])
        codable = sum(1 for v in preds.values() for e in v if e["type"] in spec.CODED_TYPES)
        print(f"\nk>={k}: {tot} concept | có mã {coded}/{codable}")
        if args.out:
            clean = strip_meta(preds)
            errs = validate.validate(clean)
            if errs:
                print(f"❌ {len(errs)} lỗi — KHÔNG ghi zip:")
                for e in errs[:20]:
                    print("  -", e)
                raise SystemExit(1)
            write_zip(clean, Path(args.out))
            print(f"✅ ghi {args.out}")


if __name__ == "__main__":
    main()
