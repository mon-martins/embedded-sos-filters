"""Convert canonical filter specs into a single aggregated C header.

Scans an input folder for canonical `*.json` specs (produced by prepare.py),
turns each into normalized SOS, and writes ONE `filters_coeffs.h` (UPPERCASE
#define macros) into the output folder.

    python tools/convert.py --in filters --out lib/include

Per spec:
- build SOS via prepare.zpk_to_sos (symmetrize + zpk2sos),
- emit COEFFS (5/section), N_SECTIONS, plus ORDER / GAIN / FS macros,
- the spec name -> FILTER_SOS_<NAME>_*, description -> comment.
Odd order works transparently (a 1st-order section is [b0,b1,0,a1,0]).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from codegen import render_header
from prepare import zpk_to_sos, spec_zpk


def spec_to_filter(spec: dict) -> dict:
    """Turn a canonical spec into the dict render_header() expects."""
    zeros, poles, gain = spec_zpk(spec)
    sos = zpk_to_sos(zeros, poles, gain)
    params = {
        "ORDER": spec.get("order"),
        "GAIN": spec.get("gain"),
        "FS": spec.get("fs"),
    }
    return {
        "name": spec["name"],
        "sos": sos,
        "params": params,
        "description": spec.get("description"),
    }


def collect_specs(in_dir: Path) -> list[dict]:
    """Find and load every canonical *.json spec under in_dir."""
    files = sorted(in_dir.rglob("*.json"))
    filters, seen = [], {}
    for path in files:
        spec = json.loads(path.read_text(encoding="utf-8"))
        name = spec["name"]
        if name in seen:
            raise ValueError(f"duplicate filter name {name!r}: {seen[name]} and {path}")
        seen[name] = path
        filters.append(spec_to_filter(spec))
        print(f"[convert] {name}: {filters[-1]['sos'].shape[0]} section(s), "
              f"order={spec.get('order')}, fs={spec.get('fs')}")
    return filters


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="in_dir", type=Path, default=Path("filters"),
                    help="folder scanned for canonical *.json specs (default: filters)")
    ap.add_argument("--out", dest="out_dir", type=Path, default=Path("lib/include"),
                    help="folder where filters_coeffs.h is written (default: lib/include)")
    args = ap.parse_args(argv)

    filters = collect_specs(args.in_dir)
    if not filters:
        print(f"[convert] no *.json specs found under {args.in_dir}")
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / "filters_coeffs.h"
    out.write_text(render_header(filters), encoding="utf-8")
    print(f"[convert] wrote {len(filters)} filter(s) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
