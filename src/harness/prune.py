#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TRACK A — ĐÃI BỎ concept rác khỏi bản nộp nền. Hướng CHƯA TỪNG THỬ.

    python3 -m src.harness.prune --rule spec --out out/candidates/18_prune_spec.zip
    python3 -m src.harness.prune --rule uncorroborated --min-votes 1 --out ...
    python3 -m src.harness.prune --rule spec,uncorroborated --dry     # chỉ xem, không ghi

LÝ DO TOÁN HỌC (SPEC_V2 §6-7):
  J là Jaccard trên HỢP -> khi BỎ N concept mà trong đó chỉ h phần khớp gold:
      J tăng  <=>  h < J/(1+J)
  Ngưỡng: J_assert 32.6% · J_cand 19.1%. Nghĩa là **bỏ nhóm nào mà dưới 1/3 có thật
  trong gold thì ĐIỂM TĂNG** — một cái bẫy rất rộng cửa.

  Giải ngược bản 14 vs 17 cho gold <= ~4000 concept, precision bản 14 chỉ 61-79%
  => đang mang 600-1100 concept rác. Bốn thí nghiệm sau bản 14 đều là THÊM và đều lỗ;
  chưa lượt nộp nào thử BỎ.

Đơn vị đãi bỏ là **cụm bề mặt (text, type)**, không phải từng lần nhắc: nếu một cụm là
khái niệm gold thật thì mọi lần nhắc của nó đều thật, và ngược lại. Bỏ theo cụm đúng bằng
"bỏ một NHÓM" trong công thức hoà vốn ở trên.
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.harness import spec, validate                # noqa: E402
from src.harness.build import resolve_voter, write_zip  # noqa: E402

BASE_ZIP = ROOT / "out/submitted/14_repeat_36.4914.zip"
VOTES = ROOT / "dev/votes_v2"


def norm(s: str) -> str:
    return unicodedata.normalize("NFC", s or "").strip().lower()


# ------------------------------------------------------------------ luật đãi bỏ

def _by_surface(base: dict, fn) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for v in base.values():
        for e in v:
            key = (norm(e["text"]), e["type"])
            if key in out:
                continue
            why = fn(e["text"], e["type"])
            if why:
                out[key] = why
    return out


def rule_spec(base: dict) -> dict[tuple[str, str], str]:
    """Cụm vi phạm cấm CỨNG của SPEC — mỗi luật đã trả giá bằng một lượt nộp."""
    return _by_surface(base, spec.is_banned)


def rule_onesyl(base: dict) -> dict[tuple[str, str], str]:
    """Cụm 1 âm tiết đứng trơ. CANH BẠC RIÊNG — xem chú thích spec.is_weak."""
    return _by_surface(base, spec.is_weak)


def voter_surfaces() -> tuple[dict[tuple[str, str], set[str]], list[str], set[str]]:
    """(text chuẩn hoá, type) -> tập voter ĐỘC LẬP từng trích cụm đó ở bất kỳ đâu.

    Trả kèm `covered` = tập file mà MỌI voter đều có phiếu. File nào chưa voter nào chạm tới
    thì "không ai xác nhận" chỉ có nghĩa là CHƯA CHẠY, không phải ý kiến — đãi bỏ ở đó là
    xoá nhầm concept đúng (đã bắt được khi kiểm thử: suýt xoá `thiếu men G6PD` 17 lần ở file 1
    chỉ vì voter chưa làm tới file đó).
    """
    surf: dict[tuple[str, str], set[str]] = defaultdict(set)
    names: list[str] = []
    covered: set[str] | None = None
    for f in sorted(VOTES.glob("*.json")):
        names.append(f.stem)
        votes = json.loads(f.read_text(encoding="utf-8"))
        resolved, _ = resolve_voter(votes, apply_ban=False)
        mine = {fid for fid, items in resolved.items() if items}
        covered = mine if covered is None else (covered & mine)
        for fid, items in resolved.items():
            for e in items:
                surf[(norm(e["text"]), e["type"])].add(f.stem)
                SPANS[fid].append((e["position"][0], e["position"][1], f.stem))
    return surf, names, covered or set()


# fid -> [(start, end, tên voter)] — dùng cho đối chiếu CHỒNG LẤN vị trí
SPANS: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
NO_RESCUE = False


def overlap_voters(fid: str, start: int, end: int) -> set[str]:
    """Voter nào trích một span CHỒNG LẤN span này (cùng file)?

    Cần thiết vì đối chiếu theo cụm bề mặt CHÍNH XÁC quá khắt khe: voter trích `bệnh gút`
    còn bản nền có `gút` thì hai bên nói về CÙNG một khái niệm, chỉ khác ranh giới.
    Không có luật này thì `xơ gan` · `gút` · `vảy nến` · `amoxicillin` bị xoá oan
    (đã bắt được khi soi tay danh sách đãi bỏ).
    """
    return {v for a, b, v in SPANS.get(fid, ()) if start < b and end > a}


def rule_uncorroborated(base: dict, surf: dict, names: list[str], min_votes: int,
                        covered: set[str]) -> dict[tuple[str, str], str]:
    """Cụm mà KHÔNG voter độc lập nào (hoặc < min_votes voter) trích lại.

    Voter mù hoàn toàn với bản 14. Cụm mà không ai độc lập nghĩ tới là ứng viên rác
    mạnh nhất ta có được nếu không có gold.
    """
    # Một cụm bị bỏ CHỈ KHI cả hai bằng chứng đều vắng:
    #   (1) không voter nào trích đúng cụm bề mặt đó ở bất kỳ đâu, VÀ
    #   (2) không lần nhắc nào của nó có voter trích một span CHỒNG LẤN.
    ok_overlap: set[tuple[str, str]] = set()
    seen: dict[tuple[str, str], bool] = {}
    for fid, v in base.items():
        if fid not in covered:   # chưa đủ phiếu ở file này -> KHÔNG có ý kiến, không đãi bỏ
            continue
        for e in v:
            key = (norm(e["text"]), e["type"])
            # CHẶN VÒNG LẶP LOGIC: voter được LỆNH không trích các cụm này (danh sách cấm
            # trong VOTER_TASK.md). Việc chúng vắng mặt là spec của ta dội lại, KHÔNG phải
            # ý kiến độc lập — không được tính là bằng chứng. Chúng thuộc rule spec/onesyl.
            if spec.is_banned(e["text"], e["type"]) or spec.is_weak(e["text"], e["type"]):
                continue
            seen[key] = True
            if not NO_RESCUE and \
                    len(overlap_voters(fid, e["position"][0], e["position"][1])) >= min_votes:
                ok_overlap.add(key)

    out: dict[tuple[str, str], str] = {}
    for key in seen:
        if len(surf.get(key, ())) >= min_votes or key in ok_overlap:
            continue
        out[key] = f"0/{len(names)} voter trích lại, và không span nào chồng lấn"
    return out


# ------------------------------------------------------------------ áp dụng

def apply_prune(base: dict, drop: dict[tuple[str, str], str],
                covered: set[str] | None = None) -> tuple[dict, Counter]:
    """`covered=None` = áp cho mọi file. Ngược lại chỉ đãi bỏ trong file đã đủ phiếu —
    file thiếu phiếu thì ta KHÔNG có ý kiến, giữ nguyên bản nền."""
    out, stats = {}, Counter()
    for fid, items in base.items():
        if covered is not None and fid not in covered:
            out[fid] = list(items)
            stats["file giữ nguyên (thiếu phiếu)"] += 0
            continue
        keep = []
        for e in items:
            key = (norm(e["text"]), e["type"])
            if key in drop:
                stats[drop[key]] += 1
            else:
                keep.append(e)
        out[fid] = keep
    return out, stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="",
                    help="zip nền để chồng lên (mặc định: bản 14). Cho phép nối các bước: span_fix -> assert -> prune ...")
    ap.add_argument("--rule", default="spec", help="spec | uncorroborated | cả hai, ngăn bởi dấu phẩy")
    ap.add_argument("--min-votes", type=int, default=1,
                    help="cụm cần >= bấy nhiêu voter độc lập mới được GIỮ")
    ap.add_argument("--no-overlap-rescue", action="store_true",
                    help="LIỀU MẠNH: bỏ cả cụm mà voter có trích span CHỒNG LẤN. Lá chắn chồng lấn "
                         "vốn để cứu `xo gan`/`gut` (voter viết `benh gut`), nhưng bản 38 đã chứng "
                         "minh đãi bỏ có lời (+0.176/49 concept) nên liều mạnh đáng đo.")
    ap.add_argument("--types", default="",
                    help="chỉ đãi bỏ trong các type này (mặc định: tất cả)")
    ap.add_argument("--out", default="")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    base = validate.load_zip(Path(args.base) if args.base else BASE_ZIP)
    n0 = sum(len(v) for v in base.values())
    rules = [r.strip() for r in args.rule.split(",") if r.strip()]

    drop: dict[tuple[str, str], str] = {}
    covered: set[str] | None = None
    if "spec" in rules:
        drop.update(rule_spec(base))
    if "onesyl" in rules:
        drop.update(rule_onesyl(base))
    if "uncorroborated" in rules:
        globals()["NO_RESCUE"] = args.no_overlap_rescue
        if not list(VOTES.glob("*.json")):
            raise SystemExit(f"Chưa có phiếu trong {VOTES} — chạy voter + merge_parts trước.")
        surf, names, covered = voter_surfaces()
        print(f"voter độc lập: {names} | file MỌI voter đều có phiếu: {len(covered)}/100")
        if len(covered) < 100:
            miss = sorted(set(base) - covered, key=int)
            print(f"⚠️  {len(miss)} file KHÔNG đãi bỏ vì thiếu phiếu: {miss[:25]}")
        drop.update(rule_uncorroborated(base, surf, names, args.min_votes, covered))

    if args.types:
        want = {t.strip() for t in args.types.split(",")}
        drop = {k: v for k, v in drop.items() if k[1] in want}

    pruned, stats = apply_prune(base, drop, covered)
    n1 = sum(len(v) for v in pruned.values())
    print(f"\nBỎ {n0-n1}/{n0} concept ({(n0-n1)/n0*100:.1f}%) — thuộc {len(drop)} cụm bề mặt")
    for why, n in stats.most_common():
        print(f"   {n:5d}  {why}")

    # Điểm hoà vốn: bỏ nhóm này chỉ lỗ nếu >32.6% trong đó thật sự có trong gold
    ty = Counter(e["type"] for fid in base for e in base[fid]
                 if (norm(e["text"]), e["type"]) in drop)
    print("\nphân bố concept bị bỏ theo type:")
    for k, n in ty.most_common():
        print(f"   {k:22s} {n:5d}")
    coded = sum(n for k, n in ty.items() if k in spec.CODED_TYPES)
    print(f"\nngưỡng hoà vốn: bỏ có LỜI nếu <{spec.BREAKEVEN_ASSERT*100:.1f}% số này có trong gold"
          f" ({coded} concept đụng thêm trục J_cand, ngưỡng {spec.BREAKEVEN_CAND*100:.1f}%)")

    print("\n30 cụm bị bỏ nhiều lần nhắc nhất:")
    per = Counter()
    for fid in base:
        for e in base[fid]:
            k = (norm(e["text"]), e["type"])
            if k in drop:
                per[k] += 1
    for (t, ty_), n in per.most_common(30):
        print(f"   {n:4d}×  {ty_:20s} {t[:44]!r}   <- {drop[(t, ty_)][:46]}")

    if args.dry or not args.out:
        return
    errs = validate.validate(pruned)
    if errs:
        print(f"\n❌ {len(errs)} lỗi — KHÔNG ghi zip")
        for e in errs[:20]:
            print("  -", e)
        raise SystemExit(1)
    write_zip(pruned, Path(args.out))
    print(f"\n✅ ghi {args.out}  ({n1} concept)")


if __name__ == "__main__":
    main()
