"""Apply LLM breakthrough decisions vào base 85 và xuất zip nộp.

Input:
  - data/teacher_85 làm nền
  - data/teacher_87 làm nguồn entity mới
  - artifacts/breakthrough/adjudicate_decisions.jsonl
  - artifacts/breakthrough/candidate_decisions.jsonl
"""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_jsonl(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text("utf-8").splitlines():
        if line.strip():
            obj = json.loads(line)
            if obj.get("id"):
                out[obj["id"]] = obj
    return out


def load_teacher(tag: str) -> dict[str, list[dict]]:
    d = ROOT / "data" / f"teacher_{tag}"
    return {p.name: json.loads(p.read_text("utf-8")) for p in sorted(d.glob("*.json"), key=lambda p: int(p.stem))}


def ent_key(e: dict) -> tuple[int, int, str]:
    s, t = e["position"]
    return int(s), int(t), e["type"]


def make_id(fname: str, e: dict) -> str:
    s, t = e["position"]
    return f"{Path(fname).stem}:{s}:{t}:{e['type']}"


def validate(fname: str, ents: list[dict]) -> None:
    raw = (ROOT / "input" / fname.replace(".json", ".txt")).read_text("utf-8")
    last = -1
    for e in sorted(ents, key=ent_key):
        s, t = e["position"]
        if raw[s:t] != e["text"]:
            raise SystemExit(f"{fname}: offset lệch {e!r}")
        if s < last:
            raise SystemExit(f"{fname}: span chồng nhau {e!r}")
        last = t


def write_zip(out_dir: Path, out_zip: Path) -> None:
    if out_zip.exists():
        out_zip.unlink()
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted((out_dir / "output").glob("*.json"), key=lambda p: int(p.stem)):
            zf.write(p, f"output/{p.name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adjudicate", default=str(ROOT / "artifacts/breakthrough/adjudicate_decisions.jsonl"))
    ap.add_argument("--candidates", default=str(ROOT / "artifacts/breakthrough/candidate_decisions.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "artifacts/breakthrough/breakthrough_llm.zip"))
    args = ap.parse_args()

    base = load_teacher("85")
    extra = load_teacher("87")
    adjud = read_jsonl(Path(args.adjudicate))
    cand = read_jsonl(Path(args.candidates))
    out_zip = Path(args.out)
    out_dir = out_zip.with_suffix("")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "output").mkdir(parents=True)

    kept = dropped = added = changed_c = changed_a = 0
    for fid in range(1, 101):
        fname = f"{fid}.json"
        ents = [dict(e) for e in base[fname]]
        present = {ent_key(e): e for e in ents}

        # Drop base entities only when LLM explicitly says keep=false.
        filtered = []
        for e in ents:
            dec = adjud.get(make_id(fname, e))
            if dec and dec.get("keep") is False:
                dropped += 1
                continue
            filtered.append(e)
        ents = filtered
        present = {ent_key(e): e for e in ents}

        # Add 87-only entities only when LLM explicitly says keep=true.
        for e in extra[fname]:
            if ent_key(e) in present:
                continue
            dec = adjud.get(make_id(fname, e))
            if dec and dec.get("keep") is True:
                ne = dict(e)
                if isinstance(dec.get("assertions"), list):
                    ne["assertions"] = [x for x in dec["assertions"] if x]
                    changed_a += 1
                ents.append(ne)
                present[ent_key(ne)] = ne
                added += 1

        # Apply candidate rerank to all entities by id.
        for e in ents:
            dec = cand.get(make_id(fname, e))
            if dec and isinstance(dec.get("candidates"), list):
                new = [str(x) for x in dec["candidates"] if str(x).strip()][:1]
                if new != (e.get("candidates") or []):
                    e["candidates"] = new
                    changed_c += 1
            deca = adjud.get(make_id(fname, e))
            if deca and isinstance(deca.get("assertions"), list):
                newa = [str(x) for x in deca["assertions"] if str(x).strip()]
                if newa != (e.get("assertions") or []):
                    e["assertions"] = newa
                    changed_a += 1

        ents.sort(key=ent_key)
        validate(fname, ents)
        kept += len(ents)
        (out_dir / "output" / fname).write_text(json.dumps(ents, ensure_ascii=False, indent=2), "utf-8")

    write_zip(out_dir, out_zip)
    print(f"kept={kept} added={added} dropped={dropped} changed_candidates={changed_c} changed_assertions={changed_a}")
    print("->", out_zip)


if __name__ == "__main__":
    main()
