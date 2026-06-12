"""Canonical filter spec <-> pyfda pole-zero export (core + CLI).

The pyfda export is "messy": only zpk, as rounded strings, in three equivalent
formats (.csv / .npy / .npz), with no metadata. This module isolates all of
that and converts, both ways, between:

    raw pole-zero export  <-->  canonical <name>.json spec

The canonical spec is the single source of truth consumed by convert/validate.

This file holds the importable, testable core plus a small CLI:

    python tools/prepare.py csv2json filters/filter_1.csv --fs 48000
    python tools/prepare.py json2csv filters/filter_1.json

The PyQt5 GUI front-end lives in tools/prepare_gui.py and calls these
functions.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
from scipy import signal


# Suggested template for the spec's free-text description (items optional).
DESCRIPTION_TEMPLATE = (
    "Specification:\n"
    "- type: \n"
    "- fc [Hz]: \n"
    "- fp [Hz]: \n"
    "- delta_p: \n"
    "- delta_s: \n"
    "\n"
    "Application:\n"
    "- where/how it will be used: \n"
    "- constraints: "
)


# --------------------------------------------------------------------------- #
# Raw pyfda export  ->  numeric zpk
# --------------------------------------------------------------------------- #
def load_zpk_array(path: Path) -> np.ndarray:
    """Load the raw (N,3) string array from .csv/.npy/.npz."""
    suffix = path.suffix.lower()
    if suffix == ".npz":
        with np.load(path, allow_pickle=True) as z:
            key = "zpk" if "zpk" in z.files else z.files[0]
            return np.atleast_2d(z[key])
    if suffix == ".npy":
        return np.atleast_2d(np.load(path, allow_pickle=True))
    if suffix == ".csv":
        rows = [ln.split(",") for ln in path.read_text(encoding="utf-8").splitlines()
                if ln.strip()]
        return np.array(rows, dtype="<U64")
    raise ValueError(f"unsupported export type: {suffix} (expected .csv/.npy/.npz)")


def parse_zpk(arr: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Parse the (N,3) string array into numeric zeros, poles, gain."""
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError(f"expected a (N,3) array, got {arr.shape}")

    def col_to_complex(col):
        return np.array([complex(str(s).strip()) for s in col if str(s).strip() != ""],
                        dtype=complex)

    zeros = col_to_complex(arr[:, 0])
    poles = col_to_complex(arr[:, 1])
    gain = float(str(arr[0, 2]).strip())
    return zeros, poles, gain


def symmetrize(roots: np.ndarray, tol: float = 1e-6) -> np.ndarray:
    """Snap near-conjugate roots to exact conjugate pairs (real imag for reals).

    pyfda rounds the exported values, so a+bj and a-bj differ slightly and
    scipy.zpk2sos rejects them. Averaging each pair restores exact symmetry.
    """
    roots = np.asarray(roots, dtype=complex)
    used = np.zeros(len(roots), bool)
    out: list[complex] = []
    for i in range(len(roots)):
        if used[i]:
            continue
        r = roots[i]
        if abs(r.imag) < tol:
            out.append(complex(r.real, 0.0))
            used[i] = True
            continue
        candidates = [k for k in range(len(roots)) if not used[k] and k != i]
        if not candidates:
            raise ValueError(f"complex root {r} has no conjugate partner")
        j = min(candidates, key=lambda k: abs(roots[k] - np.conj(r)))
        re = 0.5 * (r.real + roots[j].real)
        im = 0.5 * (abs(r.imag) + abs(roots[j].imag))
        out += [complex(re, im), complex(re, -im)]
        used[i] = used[j] = True
    return np.array(out, dtype=complex)


# --------------------------------------------------------------------------- #
# Canonical spec
# --------------------------------------------------------------------------- #
def zpk_to_sos(zeros, poles, gain: float) -> np.ndarray:
    """Symmetrize near-conjugate pairs, then scipy.zpk2sos.

    Symmetrization (snapping pyfda's rounded conjugates) happens HERE, at the
    moment of conversion -- never on the stored spec. This keeps the canonical
    JSON / pole-zero CSV faithful to pyfda's original export, while still
    feeding scipy a well-conditioned, exactly-symmetric zpk.
    """
    z = symmetrize(np.asarray(zeros, dtype=complex))
    p = symmetrize(np.asarray(poles, dtype=complex))
    return signal.zpk2sos(z, p, float(gain))


def build_spec(name: str, zeros, poles, gain: float, *,
               fs: float | None = None, description: str | None = None,
               source: str | None = None) -> dict:
    """Assemble the canonical spec dict from numeric zpk + metadata.

    The stored zeros/poles are kept **as given** (faithful to pyfda); only a
    symmetrized copy is used to derive n_sections / validate convertibility.
    """
    zeros = np.asarray(zeros, dtype=complex)
    poles = np.asarray(poles, dtype=complex)
    sos = zpk_to_sos(zeros, poles, gain)  # symmetrized copy: n_sections + validation
    return {
        "name": name,
        "description": DESCRIPTION_TEMPLATE if description is None else description,
        "fs": fs,
        "order": int(len(poles)),
        "n_sections": int(sos.shape[0]),
        "gain": float(gain),
        "zeros": [[z.real, z.imag] for z in zeros],
        "poles": [[p.real, p.imag] for p in poles],
        "source": source,
    }


def spec_zpk(spec: dict) -> tuple[np.ndarray, np.ndarray, float]:
    """Return numeric (zeros, poles, gain) from a canonical spec."""
    zeros = np.array([complex(r, i) for r, i in spec["zeros"]], dtype=complex)
    poles = np.array([complex(r, i) for r, i in spec["poles"]], dtype=complex)
    return zeros, poles, float(spec["gain"])


def dump_spec(spec: dict) -> str:
    """JSON with each [re, im] pair kept on a single line for readability."""
    text = json.dumps(spec, indent=2, ensure_ascii=False)
    return re.sub(r"\[\s+(-?[\d.eE+\-]+),\s+(-?[\d.eE+\-]+)\s+\]", r"[\1, \2]", text)


# --------------------------------------------------------------------------- #
# Conversions (both directions)
# --------------------------------------------------------------------------- #
def csv_to_spec(export_path: Path, *, name: str | None = None,
                fs: float | None = None, description: str | None = None) -> dict:
    """Raw pyfda export -> canonical spec (parse + symmetrize + metadata)."""
    arr = load_zpk_array(export_path)
    zeros, poles, gain = parse_zpk(arr)  # faithful: no symmetrize, original order
    return build_spec(name or export_path.stem, zeros, poles, gain,
                      fs=fs, description=description, source=export_path.name)


def _fmt_root(value) -> str:
    """Format a root like pyfda: a plain real if imag == 0, else (re+imj)."""
    c = complex(value)
    return repr(c.real) if c.imag == 0.0 else str(c)


def spec_to_csv_text(spec: dict) -> str:
    """Canonical spec -> pyfda-style pole-zero CSV text.

    Columns: zeros, poles, gain (gain only on the first row, like pyfda).
    Real roots are written as plain floats (e.g. -1.0) and complex roots as
    (re+imj). No trailing newline, matching pyfda's export so the round-trip
    is byte-faithful.
    """
    zeros, poles, gain = spec_zpk(spec)
    n = max(len(zeros), len(poles))
    lines = []
    for i in range(n):
        z = _fmt_root(zeros[i]) if i < len(zeros) else ""
        p = _fmt_root(poles[i]) if i < len(poles) else ""
        k = repr(gain) if i == 0 else "0.0"
        lines.append(f"{z},{p},{k}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI (scripting / tests). The GUI is in prepare_gui.py.
# --------------------------------------------------------------------------- #
def _cmd_csv2json(args) -> int:
    spec = csv_to_spec(args.export, name=args.name, fs=args.fs,
                       description=args.description)
    out = args.out or args.export.with_name(f"{spec['name']}.json")
    out.write_text(dump_spec(spec) + "\n", encoding="utf-8")
    print(f"[prepare] {spec['name']}: order={spec['order']}, "
          f"n_sections={spec['n_sections']}, gain={spec['gain']}, fs={spec['fs']}")
    print(f"[prepare] wrote spec -> {out}")
    return 0


def _cmd_json2csv(args) -> int:
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    out = args.out or args.spec.with_name(f"{spec['name']}_polezero.csv")
    out.write_text(spec_to_csv_text(spec), encoding="utf-8")
    print(f"[prepare] wrote pole-zero CSV -> {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("csv2json", help="raw pyfda export -> canonical spec")
    c.add_argument("export", type=Path, help="raw pyfda export (.csv/.npy/.npz)")
    c.add_argument("--name", help="filter name (default: export file stem)")
    c.add_argument("--fs", type=float, help="sampling frequency (Hz)")
    c.add_argument("--description", help="description text (default: template)")
    c.add_argument("--out", type=Path, help="output .json path")
    c.set_defaults(func=_cmd_csv2json)

    j = sub.add_parser("json2csv", help="canonical spec -> pole-zero CSV")
    j.add_argument("spec", type=Path, help="canonical <name>.json")
    j.add_argument("--out", type=Path, help="output .csv path")
    j.set_defaults(func=_cmd_json2csv)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
