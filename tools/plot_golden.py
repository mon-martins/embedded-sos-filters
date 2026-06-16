"""Plot the C-library output vs scipy.sosfilt for a filter spec.

Compiles lib/source_c/sos_filter.c, feeds the filter's float32 coefficients
through ctypes, and plots the C output against scipy.sosfilt plus the error,
for impulse / step / noise. Writes one PNG per spec into --out.

Generic: works for any spec (CSV pole-zero export or canonical JSON), no
per-filter wrapper needed. Meant to run where `cc` is a 64-bit gcc, e.g. the
project Docker image:

    docker compose run --rm tests python tools/plot_golden.py filters/foo.json --out build/golden
"""
from __future__ import annotations

import argparse
import ctypes
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")  # headless: write PNGs, no GUI window
import matplotlib.pyplot as plt
from scipy import signal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare as P

ROOT = Path(__file__).resolve().parents[1]
INC = ROOT / "lib" / "include"
DATA = ROOT / "tests" / "data"          # mcu_types.h stand-in
SRC_C = ROOT / "lib" / "source_c" / "sos_filter.c"

_c_float_p = ctypes.POINTER(ctypes.c_float)


class _SosFilt(ctypes.Structure):
    _fields_ = [("coeffs", _c_float_p),
                ("state", _c_float_p),
                ("n_sections", ctypes.c_uint8)]


def load_spec(path: Path) -> dict:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if path.suffix.lower() in (".csv", ".npy", ".npz"):
        return P.csv_to_spec(path)
    raise ValueError(f"unsupported input: {path.suffix} (expected .csv/.npy/.npz/.json)")


def build_lib(tmp: Path):
    """Compile sos_filter.c into a shared library and bind it via ctypes."""
    cc = next((c for c in ("cc", "gcc", "clang") if shutil.which(c)), None)
    if cc is None:
        raise RuntimeError("no C compiler (cc/gcc/clang) on PATH")
    out = tmp / ("libsos.dll" if platform.system() == "Windows" else "libsos.so")
    subprocess.run(
        [cc, "-O2", "-std=c99", "-fPIC", "-shared", "-o", str(out),
         "-I", str(INC), "-I", str(DATA), str(SRC_C)],
        check=True, capture_output=True, text=True)
    lib = ctypes.CDLL(str(out))
    lib.sos_init.argtypes = [ctypes.POINTER(_SosFilt), _c_float_p, _c_float_p,
                             ctypes.c_uint8]
    lib.sos_init.restype = None
    lib.sos_process_block.argtypes = [ctypes.POINTER(_SosFilt), _c_float_p,
                                      _c_float_p, ctypes.c_size_t]
    lib.sos_process_block.restype = None
    return lib


def run_c(lib, coeffs5, n_sections, x):
    coeffs = (ctypes.c_float * len(coeffs5))(*coeffs5.tolist())
    state = (ctypes.c_float * (2 * n_sections))()
    f = _SosFilt()
    lib.sos_init(ctypes.byref(f), coeffs, state, n_sections)
    cin = (ctypes.c_float * len(x))(*x.tolist())
    cout = (ctypes.c_float * len(x))()
    lib.sos_process_block(ctypes.byref(f), cin, cout, len(x))
    return np.frombuffer(cout, dtype=np.float32).astype(np.float64)


def _signals(n=2048):
    rng = np.random.default_rng(0)  # fixed seed: reproducible
    impulse = np.zeros(n); impulse[0] = 1.0
    return {"impulse": impulse, "step": np.ones(n), "noise": rng.standard_normal(n)}


def compute(spec: dict, lib) -> dict:
    """Run every test signal through the C lib and scipy; return {sig: (ref, got)}."""
    sos = P.zpk_to_sos(*P.spec_zpk(spec))
    coeffs5 = sos[:, [0, 1, 2, 4, 5]].astype(np.float32).flatten()
    out = {}
    for name, x in _signals().items():
        ref = signal.sosfilt(sos.astype(np.float64), x.astype(np.float64))
        got = run_c(lib, coeffs5, sos.shape[0], x)
        out[name] = (ref, got)
    return out


def render_png(spec: dict, results: dict, out_dir: Path) -> Path:
    fig, axes = plt.subplots(len(results), 2, figsize=(12, 8))
    for row, (name, (ref, got)) in enumerate(results.items()):
        err = got - ref
        ax_o, ax_e = axes[row]
        ax_o.plot(ref, color="C1", lw=1.4, label="scipy.sosfilt (ref)")
        ax_o.plot(got, color="C0", lw=0.8, ls="--", label="C output (float32)")
        ax_o.set_ylabel(name); ax_o.grid(True); ax_o.legend(loc="upper right", fontsize=8)
        ax_e.plot(err, color="C3", lw=0.8)
        ax_e.set_ylabel(f"error\nmax={np.max(np.abs(err)):.2e}"); ax_e.grid(True)
    axes[0, 0].set_title(f"{spec['name']} - C output vs scipy")
    axes[0, 1].set_title("error (C - scipy)")
    axes[-1, 0].set_xlabel("Sample"); axes[-1, 1].set_xlabel("Sample")
    fig.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{spec['name']}_c_vs_scipy.png"
    fig.savefig(path, dpi=120); plt.close(fig)
    return path


def dump_npz(spec: dict, results: dict, out_dir: Path) -> Path:
    """Save the raw arrays so a host GUI can render them interactively."""
    data = {"filter_name": spec["name"], "_signal_names": np.array(list(results))}
    for name, (ref, got) in results.items():
        data[f"{name}_ref"] = ref
        data[f"{name}_got"] = got
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{spec['name']}.npz"
    np.savez(path, **data)
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", type=Path, nargs="+", help="pole-zero CSV or JSON spec(s)")
    ap.add_argument("--out", type=Path, default=Path("build/golden"),
                    help="folder for the PNG plots (default: build/golden)")
    ap.add_argument("--npz", type=Path, default=None,
                    help="also dump raw arrays as <name>.npz into this folder")
    args = ap.parse_args(argv)

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        lib = build_lib(Path(tmp))
        for path in args.inputs:
            spec = load_spec(path)
            results = compute(spec, lib)
            png = render_png(spec, results, args.out)
            print(f"[plot_golden] {spec['name']}: wrote {png}")
            if args.npz is not None:
                npz = dump_npz(spec, results, args.npz)
                print(f"[plot_golden] {spec['name']}: wrote {npz}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
