"""Validate a filter by simulation, producing plots + a report for review.

For each input (a pole-zero CSV or a canonical JSON spec) it writes, into
<out>/<name>/, four diagrams plus report.txt for MANUAL confirmation:

  01_frequency_response.png  SOS cascade vs the direct (b,a) form (mag + phase)
  02_time_vs_reference.png   own DF2T simulation vs scipy.sosfilt
  03_pole_zero.png           pole-zero map; flags poles on/outside the unit circle
  04_float32_error.png       float32 vs float64 DF2T error (RMS, worst, overflow)

The DF2T simulation mirrors the C runtime library exactly:
    y     = b0*x + s0
    s0'   = b1*x - a1*y + s1
    s1'   = b2*x - a2*y

Usage:
    python tools/validate.py tests/data/filter_order7.csv filters/foo.json
    python tools/validate.py --out build/validation tests/data/*.csv
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")  # headless: write PNGs, no GUI window
import matplotlib.pyplot as plt
from scipy import signal

from prepare import csv_to_spec, spec_zpk, symmetrize, zpk_to_sos


def load_spec(path: Path) -> dict:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if path.suffix.lower() == ".csv":
        return csv_to_spec(path)
    raise ValueError(f"unsupported input: {path.suffix} (expected .csv/.json)")


def df2t_simulate(sos: np.ndarray, x: np.ndarray, dtype=np.float64) -> np.ndarray:
    """Cascaded Direct Form II Transposed simulation (mirrors the C lib)."""
    sos = sos.astype(dtype)
    x = x.astype(dtype)
    state = np.zeros((sos.shape[0], 2), dtype=dtype)
    y = np.empty_like(x)
    for n in range(x.shape[0]):
        s = dtype(x[n])
        for i in range(sos.shape[0]):
            b0, b1, b2, _a0, a1, a2 = sos[i]
            out = dtype(b0 * s + state[i, 0])
            state[i, 0] = dtype(b1 * s - a1 * out + state[i, 1])
            state[i, 1] = dtype(b2 * s - a2 * out)
            s = out
        y[n] = s
    return y


def _test_signals(n: int, fs: float) -> dict[str, np.ndarray]:
    t = np.arange(n) / fs
    rng = np.random.default_rng(0)  # fixed seed: reproducible plots
    impulse = np.zeros(n); impulse[0] = 1.0
    step = np.ones(n)
    noise = rng.standard_normal(n)
    chirp = signal.chirp(t, f0=0.0, f1=fs / 2.0, t1=t[-1] if n > 1 else 1.0)
    return {"impulse": impulse, "step": step, "noise": noise, "chirp": chirp}


def _db(h):
    return 20.0 * np.log10(np.maximum(np.abs(h), 1e-12))


def print_sos(name: str, sos: np.ndarray) -> list[str]:
    lines = [f"{name}: {sos.shape[0]} section(s)  [b0, b1, b2 | a0, a1, a2]"]
    for i, r in enumerate(sos):
        first = " (1st-order)" if r[2] == 0.0 and r[5] == 0.0 else ""
        lines.append(f"  section {i}{first}: "
                     f"b=[{r[0]: .8g}, {r[1]: .8g}, {r[2]: .8g}]  "
                     f"a=[{r[3]: .8g}, {r[4]: .8g}, {r[5]: .8g}]")
    return lines


def check_freq_response(spec, sos, outdir) -> list[str]:
    z, p, k = spec_zpk(spec)
    b, a = signal.zpk2tf(symmetrize(z), symmetrize(p), k)
    fs = spec.get("fs")
    worN = 8192
    if fs:
        w_s, h_s = signal.sosfreqz(sos, worN=worN, fs=fs)
        w_d, h_d = signal.freqz(b, a, worN=worN, fs=fs)
        xs, xd, xlabel = w_s, w_d, "Frequency [Hz]"
    else:
        w_s, h_s = signal.sosfreqz(sos, worN=worN)
        w_d, h_d = signal.freqz(b, a, worN=worN)
        xs, xd, xlabel = w_s / np.pi, w_d / np.pi, "Normalized frequency  (x pi rad/sample)"

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    ax1.plot(xd, _db(h_d), color="C1", lw=1.6, label="direct (b, a)")
    ax1.plot(xs, _db(h_s), color="C0", lw=1.0, ls="--", label="SOS cascade")
    ax1.set_ylabel("Magnitude [dB]"); ax1.grid(True); ax1.legend(fontsize=9)
    ax1.set_title(f"{spec['name']} - frequency response: SOS vs direct")
    ax2.plot(xd, np.unwrap(np.angle(h_d)), color="C1", lw=1.6)
    ax2.plot(xs, np.unwrap(np.angle(h_s)), color="C0", lw=1.0, ls="--")
    ax2.set_ylabel("Phase [rad]"); ax2.set_xlabel(xlabel); ax2.grid(True)
    fig.tight_layout(); fig.savefig(outdir / "01_frequency_response.png", dpi=120)
    plt.close(fig)

    return [f"  freq: max|mag_SOS - mag_direct| = {np.max(np.abs(_db(h_s) - _db(h_d))):.3e} dB"]


def check_time_vs_reference(spec, sos, outdir) -> list[str]:
    n, fs = 2048, (spec.get("fs") or 1.0)
    sigs = _test_signals(n, fs)
    fig, axes = plt.subplots(len(sigs), 1, figsize=(9, 9), sharex=True)
    report = []
    for ax, (sig_name, x) in zip(axes, sigs.items()):
        ref = signal.sosfilt(sos, x.astype(np.float64))
        own = df2t_simulate(sos, x, dtype=np.float64)
        report.append(f"  time[{sig_name}]: max|own - sosfilt| = {np.max(np.abs(ref - own)):.3e}")
        ax.plot(ref, color="C1", lw=1.2, label="scipy.sosfilt (ref)")
        ax.plot(own, color="C0", lw=0.8, ls="--", label="own DF2T")
        ax.set_ylabel(sig_name); ax.grid(True); ax.legend(loc="upper right", fontsize=8)
    axes[0].set_title(f"{spec['name']} - time-domain output vs reference")
    axes[-1].set_xlabel("Sample")
    fig.tight_layout(); fig.savefig(outdir / "02_time_vs_reference.png", dpi=120)
    plt.close(fig)
    return report


def check_stability(spec, sos, outdir) -> list[str]:
    report, fig = [], plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(1, 1, 1)
    theta = np.linspace(0, 2 * np.pi, 512)
    ax.plot(np.cos(theta), np.sin(theta), "k--", lw=0.8)
    worst = 0.0
    for i, sec in enumerate(sos):
        zz, pp, _ = signal.tf2zpk(sec[:3], sec[3:])
        ax.scatter(np.real(zz), np.imag(zz), marker="o", facecolors="none",
                   edgecolors="C0", label="zeros" if i == 0 else None)
        ax.scatter(np.real(pp), np.imag(pp), marker="x", color="C3",
                   label="poles" if i == 0 else None)
        rmax = float(np.max(np.abs(pp))) if len(pp) else 0.0
        worst = max(worst, rmax)
        report.append(f"  section {i}: max|pole| = {rmax:.6f}"
                      + ("  <-- UNSTABLE" if rmax >= 1.0 else ""))
    ax.set_aspect("equal"); ax.grid(True); ax.legend(loc="upper right", fontsize=8)
    ax.set_title(f"{spec['name']} - pole-zero map (unit circle dashed)")
    fig.tight_layout(); fig.savefig(outdir / "03_pole_zero.png", dpi=120)
    plt.close(fig)
    report.append(f"  stability: worst |pole| = {worst:.6f} -> "
                  + ("STABLE" if worst < 1.0 else "UNSTABLE"))
    return report


def check_float32(spec, sos, outdir) -> list[str]:
    n, fs = 4096, (spec.get("fs") or 1.0)
    x = _test_signals(n, fs)["noise"]
    ref64 = df2t_simulate(sos, x, dtype=np.float64)
    out32 = df2t_simulate(sos, x, dtype=np.float32).astype(np.float64)
    diff = ref64 - out32
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(diff)
    ax.set_title(f"{spec['name']} - float32 DF2T error (own32 - own64), noise input")
    ax.set_xlabel("Sample"); ax.set_ylabel("Error"); ax.grid(True)
    fig.tight_layout(); fig.savefig(outdir / "04_float32_error.png", dpi=120)
    plt.close(fig)
    return [
        f"  float32: RMS error    = {np.sqrt(np.mean(diff ** 2)):.3e}",
        f"  float32: worst error  = {np.max(np.abs(diff)):.3e}",
        f"  float32: output peak  = {np.max(np.abs(out32)):.3e}",
        f"  float32: overflow/NaN = {not np.all(np.isfinite(out32))}",
    ]


def validate_one(path: Path, out_base: Path) -> None:
    spec = load_spec(path)
    z, p, k = spec_zpk(spec)
    sos = zpk_to_sos(z, p, k)
    outdir = out_base / spec["name"]
    outdir.mkdir(parents=True, exist_ok=True)

    report = print_sos(spec["name"], sos)
    report += check_freq_response(spec, sos, outdir)
    report += check_time_vs_reference(spec, sos, outdir)
    report += check_stability(spec, sos, outdir)
    report += check_float32(spec, sos, outdir)

    text = "\n".join(report)
    (outdir / "report.txt").write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"  -> plots + report in {outdir}\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", type=Path, nargs="+", help="pole-zero CSV or JSON spec(s)")
    ap.add_argument("--out", type=Path, default=Path("build/validation"),
                    help="output folder (default: build/validation)")
    args = ap.parse_args(argv)
    for path in args.inputs:
        validate_one(path, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
