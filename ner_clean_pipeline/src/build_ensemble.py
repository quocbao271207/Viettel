"""Build leaderboard-probe ensembles from the NER submission and teammate outputs.

This is intentionally a Phase-1 tool. It combines public-test submissions to learn which
axis still has signal:

- teammate14 has better BTC-style spans/assertions.
- local NER has stronger candidates on the 34.3271 run.

The generated zips keep the official `output/*.json` structure.
"""

from __future__ import annotations

import argparse
import collections
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ASSERTABLE = {"CHẨN_ĐOÁN", "THUỐC", "TRIỆU_CHỨNG"}

Entity = dict[str, Any]


def load_zip(zip_path: Path, out_dir: Path) -> Path:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(out_dir)
    if (out_dir / "output").is_dir():
        return out_dir / "output"
    return out_dir


def load_dir(path: Path) -> dict[str, list[Entity]]:
    return {
        p.stem: json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(path.glob("*.json"), key=lambda x: int(x.stem))
    }


def key_exact(e: Entity) -> tuple[str, tuple[int, int], str]:
    return (e.get("type", ""), tuple(e.get("position", [0, 0])), e.get("text", ""))


def key_text(e: Entity) -> tuple[str, str]:
    return (e.get("type", ""), e.get("text", "").strip().lower())


def overlap(a: Entity, b: Entity) -> int:
    if a.get("type") != b.get("type"):
        return 0
    s1, t1 = a["position"]
    s2, t2 = b["position"]
    return max(0, min(t1, t2) - max(s1, s2))


def sort_clean(arr: list[Entity]) -> list[Entity]:
    seen: set[tuple[str, tuple[int, int], str]] = set()
    out: list[Entity] = []
    for e in sorted(arr, key=lambda x: (x["position"][0], x["position"][1], x.get("type", ""))):
        k = key_exact(e)
        if k in seen:
            continue
        seen.add(k)
        out.append(e)
    return out


def with_ner_candidates(base: list[Entity], ner: list[Entity]) -> list[Entity]:
    ner_exact = {key_exact(e): e for e in ner}
    ner_text: dict[tuple[str, str], list[Entity]] = collections.defaultdict(list)
    for e in ner:
        ner_text[key_text(e)].append(e)

    out: list[Entity] = []
    for e in base:
        x = dict(e)
        ne = ner_exact.get(key_exact(e))
        if ne is None:
            candidates = ner_text.get(key_text(e), [])
            candidates = sorted(
                candidates,
                key=lambda n: (-overlap(e, n), abs(n["position"][0] - e["position"][0])),
            )
            ne = candidates[0] if candidates else None
        if ne and ne.get("candidates"):
            x["candidates"] = list(ne["candidates"])
        out.append(x)
    return sort_clean(out)


def union_priority(
    base: list[Entity],
    add: list[Entity],
    add_types: set[str] | None = None,
) -> list[Entity]:
    out = [dict(e) for e in base]
    for e in add:
        if add_types and e.get("type") not in add_types:
            continue
        duplicate = False
        for b in out:
            ov = overlap(e, b)
            if not ov:
                continue
            len_e = e["position"][1] - e["position"][0]
            len_b = b["position"][1] - b["position"][0]
            if ov / max(1, min(len_e, len_b)) >= 0.5:
                duplicate = True
                break
        if not duplicate:
            out.append(dict(e))
    return sort_clean(out)


def intersection_like(a: list[Entity], b: list[Entity]) -> list[Entity]:
    out: list[Entity] = []
    for e in a:
        ok = False
        for x in b:
            ov = overlap(e, x)
            if not ov:
                continue
            len_e = e["position"][1] - e["position"][0]
            len_x = x["position"][1] - x["position"][0]
            if ov / max(1, min(len_e, len_x)) >= 0.5:
                ok = True
                break
        if ok:
            out.append(dict(e))
    return sort_clean(out)


def write_variant(name: str, data: dict[str, list[Entity]], out_root: Path) -> Path:
    out_dir = out_root / name / "output"
    if out_dir.exists():
        shutil.rmtree(out_dir.parent)
    out_dir.mkdir(parents=True)

    for fid in map(str, range(1, 101)):
        raw = (ROOT / "input" / f"{fid}.txt").read_text(encoding="utf-8")
        arr = data.get(fid, [])
        for e in arr:
            s, t = e["position"]
            if raw[s:t] != e["text"]:
                raise ValueError(f"{name}/{fid}: bad offset {e!r}")
            if e.get("type") not in ASSERTABLE:
                e["assertions"] = []
        (out_dir / f"{fid}.json").write_text(
            json.dumps(arr, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    zip_path = out_root / f"{name}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(out_dir.glob("*.json"), key=lambda x: int(x.stem)):
            zf.write(p, f"output/{p.name}")
    return zip_path


def summarize(data: dict[str, list[Entity]]) -> dict[str, Any]:
    types: collections.Counter[str] = collections.Counter()
    total = cand = ass = 0
    for arr in data.values():
        total += len(arr)
        types.update(e.get("type", "") for e in arr)
        cand += sum(bool(e.get("candidates")) for e in arr)
        ass += sum(bool(e.get("assertions")) for e in arr)
    return {"entities": total, "candidates": cand, "assertions": ass, "types": dict(types)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ner-zip", default="artifacts/submissions/ner34_from_colab/output.zip")
    ap.add_argument(
        "--teammate-zip",
        default="artifacts/teammate_viettel_repo/out/submitted/14_repeat_36.4914.zip",
    )
    ap.add_argument("--out", default="artifacts/ensembles")
    args = ap.parse_args()

    out_root = ROOT / args.out
    out_root.mkdir(parents=True, exist_ok=True)
    ner_dir = load_zip(ROOT / args.ner_zip, out_root / "_ner_extract")
    teammate_dir = load_zip(ROOT / args.teammate_zip, out_root / "_teammate_extract")
    ner = load_dir(ner_dir)
    teammate = load_dir(teammate_dir)

    variants = {
        "v1_teammate14_ner_candidates": {
            fid: with_ner_candidates(teammate.get(fid, []), ner.get(fid, []))
            for fid in map(str, range(1, 101))
        },
        "v2_teammate14_plus_ner_lab": {
            fid: union_priority(
                with_ner_candidates(teammate.get(fid, []), ner.get(fid, [])),
                ner.get(fid, []),
                add_types={"TÊN_XÉT_NGHIỆM", "KẾT_QUẢ_XÉT_NGHIỆM"},
            )
            for fid in map(str, range(1, 101))
        },
        "v3_teammate14_plus_ner_all": {
            fid: union_priority(
                with_ner_candidates(teammate.get(fid, []), ner.get(fid, [])),
                ner.get(fid, []),
            )
            for fid in map(str, range(1, 101))
        },
        "v5_intersection_teammate_spans": {
            fid: intersection_like(teammate.get(fid, []), ner.get(fid, []))
            for fid in map(str, range(1, 101))
        },
    }

    print("variant\tentities\tcandidates\tassertions\tzip")
    for name, data in variants.items():
        zip_path = write_variant(name, data, out_root)
        s = summarize(data)
        print(f"{name}\t{s['entities']}\t{s['candidates']}\t{s['assertions']}\t{zip_path}")


if __name__ == "__main__":
    main()
