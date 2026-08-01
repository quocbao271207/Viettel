"""Chuẩn bị batch JSONL cho hướng đột phá: LLM adjudication + candidate rerank.

Đầu ra:

    artifacts/breakthrough/adjudicate.jsonl
    artifacts/breakthrough/candidates.jsonl

`adjudicate`: mọi span bất đồng giữa 82x/85/87/88, kèm context để LLM quyết giữ/bỏ.
`candidates`: mọi CHẨN_ĐOÁN/THUỐC trong base 85 + 87-only, kèm shortlist mã.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEACHERS = ("82x", "85", "87", "88")
CODED_TYPES = {"CHẨN_ĐOÁN", "THUỐC"}
STOP = {
    "bệnh",
    "do",
    "và",
    "hoặc",
    "của",
    "khác",
    "không",
    "xác",
    "định",
    "cấp",
    "mạn",
    "tính",
    "triệu",
    "chứng",
}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def toks(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-zA-ZÀ-ỹ0-9]+", norm(s)) if t not in STOP and len(t) > 1}


def load_teacher(tag: str) -> dict[str, list[dict]]:
    d = ROOT / "data" / f"teacher_{tag}"
    return {p.name: json.loads(p.read_text("utf-8")) for p in sorted(d.glob("*.json"), key=lambda p: int(p.stem))}


def ent_key(e: dict) -> tuple[int, int, str]:
    s, t = e["position"]
    return int(s), int(t), e["type"]


def make_id(fname: str, e: dict) -> str:
    s, t = e["position"]
    return f"{Path(fname).stem}:{s}:{t}:{e['type']}"


def context(fname: str, e: dict, width: int) -> str:
    raw = (ROOT / "input" / fname.replace(".json", ".txt")).read_text("utf-8")
    s, t = e["position"]
    return " ".join(raw[max(0, s - width) : min(len(raw), t + width)].split())


def load_icd_entries() -> list[dict]:
    kb = json.loads((ROOT / "data/kb/icd10.json").read_text("utf-8"))
    out = []
    for code, v in kb["entries"].items():
        vi, en = v.get("vi", ""), v.get("en", "")
        out.append(
            {
                "code": code,
                "vi": vi,
                "en": en,
                "vi_norm": norm(vi),
                "en_norm": norm(en),
                "tokens": toks(vi + " " + en),
            }
        )
    return out


def load_rx_entries() -> list[dict]:
    rx = json.loads((ROOT / "data/kb/rxnorm_drugs.json").read_text("utf-8"))
    return [
        {"code": str(code), "name": name, "name_norm": norm(name), "tokens": toks(name)}
        for name, code in rx.items()
    ]


def inverted(entries: list[dict], max_df: int = 500) -> dict[str, list[dict]]:
    inv: dict[str, list[dict]] = {}
    for it in entries:
        for tok in it["tokens"]:
            inv.setdefault(tok, []).append(it)
    inv = {tok: vals for tok, vals in inv.items() if len(vals) <= max_df}
    return inv


def teacher_code_votes(teachers: dict[str, dict[str, list[dict]]], fname: str, e: dict) -> list[str]:
    codes: list[str] = []
    k = ent_key(e)
    for tag in TEACHERS:
        for te in teachers[tag][fname]:
            if ent_key(te) == k or (te["type"] == e["type"] and norm(te["text"]) == norm(e["text"])):
                for c in te.get("candidates") or []:
                    if c not in codes:
                        codes.append(c)
    return codes


def score_text(q_norm: str, qtok: set[str], label_norm: str, ltok: set[str]) -> float:
    if not qtok or not ltok:
        return 0.0
    inter = len(qtok & ltok)
    if inter == 0 and q_norm not in label_norm and label_norm not in q_norm:
        return 0.0
    j = inter / len(qtok | ltok)
    sub = 0.25 if q_norm in label_norm or label_norm in q_norm else 0.0
    return j + sub + inter * 0.03


def icd_options(
    text: str, icd: list[dict], icd_inv: dict[str, list[dict]], seed: list[str], topk: int
) -> list[dict]:
    qtok = toks(text)
    qn = norm(text)
    pool = {id(it): it for tok in qtok for it in icd_inv.get(tok, [])}
    # Nếu không token nào trùng, chỉ dùng seed. Đừng quét toàn ICD: shortlist rác chỉ làm LLM nhiễu.
    ranked = []
    for it in pool.values():
        s = max(
            score_text(qn, qtok, it["vi_norm"], it["tokens"]),
            score_text(qn, qtok, it["en_norm"], it["tokens"]),
        )
        if s > 0:
            ranked.append((s, it))
    ranked.sort(key=lambda x: x[0], reverse=True)
    out, seen = [], set()
    by_code = {it["code"]: it for it in icd}
    for code in seed:
        it = by_code.get(code)
        if it and code not in seen:
            out.append({"code": code, "vi": it["vi"], "en": it["en"], "source": "teacher"})
            seen.add(code)
    for _, it in ranked:
        if it["code"] in seen:
            continue
        out.append({"code": it["code"], "vi": it["vi"], "en": it["en"], "source": "lexical"})
        seen.add(it["code"])
        if len(out) >= topk:
            break
    return out


def rx_options(
    text: str, rx_inv: dict[str, list[dict]], seed: list[str], topk: int
) -> list[dict]:
    qtok = toks(text)
    qn = norm(text)
    pool = {id(it): it for tok in qtok for it in rx_inv.get(tok, [])}
    ranked = []
    for it in pool.values():
        s = score_text(qn, qtok, it["name_norm"], it["tokens"])
        if s > 0:
            ranked.append((s, it))
    ranked.sort(key=lambda x: x[0], reverse=True)
    out, seen = [], set()
    for code in seed:
        if code not in seen:
            out.append({"code": code, "name": "", "source": "teacher"})
            seen.add(code)
    for _, it in ranked:
        if it["code"] in seen:
            continue
        out.append({"code": it["code"], "name": it["name"], "source": "lexical"})
        seen.add(it["code"])
        if len(out) >= topk:
            break
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(ROOT / "artifacts/breakthrough"))
    ap.add_argument("--ctx", type=int, default=180)
    ap.add_argument("--topk", type=int, default=15)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    teachers = {tag: load_teacher(tag) for tag in TEACHERS}
    icd = load_icd_entries()
    icd_inv = inverted(icd)
    rx = load_rx_entries()
    rx_inv = inverted(rx)

    adjudicate = []
    candidates = []
    seen_candidate_ids: set[str] = set()
    for fid in range(1, 101):
        fname = f"{fid}.json"
        all_by_key: dict[tuple[int, int, str], dict[str, dict]] = {}
        for tag in TEACHERS:
            for e in teachers[tag][fname]:
                all_by_key.setdefault(ent_key(e), {})[tag] = e
        for k, pres in sorted(all_by_key.items()):
            sample = next(iter(pres.values()))
            if len(pres) != len(TEACHERS):
                adjudicate.append(
                    {
                        "id": make_id(fname, sample),
                        "file": fname,
                        "text": sample["text"],
                        "type": sample["type"],
                        "position": sample["position"],
                        "present_in": sorted(pres),
                        "candidates": sample.get("candidates") or [],
                        "assertions": sample.get("assertions") or [],
                        "context": context(fname, sample, args.ctx),
                    }
                )
            if sample["type"] in CODED_TYPES and ("85" in pres or "87" in pres):
                src = pres.get("85") or pres.get("87") or sample
                eid = make_id(fname, src)
                if eid in seen_candidate_ids:
                    continue
                seen_candidate_ids.add(eid)
                seed = teacher_code_votes(teachers, fname, src)
                opts = (
                    icd_options(src["text"], icd, icd_inv, seed, args.topk)
                    if src["type"] == "CHẨN_ĐOÁN"
                    else rx_options(src["text"], rx_inv, seed, args.topk)
                )
                candidates.append(
                    {
                        "id": eid,
                        "file": fname,
                        "text": src["text"],
                        "type": src["type"],
                        "position": src["position"],
                        "current_candidates": src.get("candidates") or [],
                        "options": opts,
                        "context": context(fname, src, args.ctx),
                    }
                )

    (out_dir / "adjudicate.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in adjudicate) + "\n", "utf-8"
    )
    (out_dir / "candidates.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in candidates) + "\n", "utf-8"
    )
    print(f"adjudicate: {len(adjudicate)} -> {out_dir/'adjudicate.jsonl'}")
    print(f"candidates: {len(candidates)} -> {out_dir/'candidates.jsonl'}")


if __name__ == "__main__":
    main()
