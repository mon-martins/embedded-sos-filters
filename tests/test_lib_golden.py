"""Golden-vector test: per-filter C wrappers vs scipy.sosfilt.

For each fixture, a hand-written wrapper applies that filter to an array --
one via the block API, one sample by sample -- using coefficients from the
generated header, so the whole codegen + library path is exercised. The
float32 output is compared to scipy.sosfilt within a float32 tolerance.

Run via `docker compose run --rm tests`; skips if the built library can't be
loaded by the running Python (e.g. a 32-bit gcc on a 64-bit host).
"""
import ctypes
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy import signal

# Reuse the project pipeline (tools/) to build both the reference SOS and the
# generated header, so the test runs the real spec -> SOS -> codegen path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import convert as C  # noqa: E402
import prepare as P  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
INC = ROOT / "lib" / "include"          # sos_filter.h
DATA = Path(__file__).parent / "data"   # fixtures + mcu_types.h stand-in
APPLY = Path(__file__).parent / "apply"  # hand-written apply_*.c wrappers
SRC_C = ROOT / "lib" / "source_c" / "sos_filter.c"

FIXTURES = ["filter_order4", "filter_order7", "filter_order10"]
APIS = ["block", "sample"]

_CC = next((c for c in ("cc", "gcc", "clang") if shutil.which(c)), None)
pytestmark = pytest.mark.skipif(_CC is None, reason="no C compiler (cc/gcc/clang)")

_c_float_p = ctypes.POINTER(ctypes.c_float)


@pytest.fixture(scope="module")
def sos_lib(tmp_path_factory):
    """Generate the coeff header, compile lib + wrappers, return a call helper."""
    base = tmp_path_factory.mktemp("golden")

    # CSV fixtures -> JSON specs -> generated filters_coeffs.h (codegen).
    specs = base / "specs"; specs.mkdir()
    for csv in sorted(DATA.glob("*.csv")):
        spec = P.csv_to_spec(csv)
        (specs / f"{spec['name']}.json").write_text(
            P.dump_spec(spec) + "\n", encoding="utf-8")
    gen_inc = base / "include"
    assert C.main(["--in", str(specs), "--out", str(gen_inc)]) == 0

    # Compile the runtime lib + every apply wrapper into one shared library.
    # gen_inc first so the fresh filters_coeffs.h wins over any stale
    # lib/include copy (gitignored artifact from a prior run).
    out = base / ("libgolden.dll" if platform.system() == "Windows" else "libgolden.so")
    sources = [str(SRC_C), *sorted(str(p) for p in APPLY.glob("*.c"))]
    subprocess.run(
        [_CC, "-O2", "-std=c99", "-fPIC", "-shared", "-o", str(out),
         "-I", str(gen_inc), "-I", str(INC), "-I", str(DATA), *sources],
        check=True, capture_output=True, text=True)

    # check=True already raised on a compile error; an OSError here means the
    # binary built but can't run in this process -> skip.
    try:
        lib = ctypes.CDLL(str(out))
    except OSError as exc:
        pytest.skip(f"cannot load built library; run in the Docker image: {exc}")

    def call(fixture, api, x):
        fn = getattr(lib, f"apply_{fixture}_{api}")
        fn.argtypes = [_c_float_p, _c_float_p, ctypes.c_size_t]
        fn.restype = None
        cin = (ctypes.c_float * len(x))(*x.tolist())
        cout = (ctypes.c_float * len(x))()
        fn(cin, cout, len(x))
        return np.frombuffer(cout, dtype=np.float32).astype(np.float64)

    return call


def _signals(n=2048):
    """Three deterministic test signals: impulse, step, and white noise."""
    rng = np.random.default_rng(0)  # fixed seed: reproducible vectors
    impulse = np.zeros(n); impulse[0] = 1.0
    return {"impulse": impulse, "step": np.ones(n), "noise": rng.standard_normal(n)}


@pytest.mark.parametrize("fixture", FIXTURES)
@pytest.mark.parametrize("api", APIS)
@pytest.mark.parametrize("sig_name", ["impulse", "step", "noise"])
def test_apply_matches_scipy(sos_lib, fixture, api, sig_name):
    # Reference SOS (same coeffs the header bakes in, up to float32 rounding).
    spec = P.csv_to_spec(DATA / f"{fixture}.csv")
    sos = P.zpk_to_sos(*P.spec_zpk(spec))

    x = _signals()[sig_name]
    ref = signal.sosfilt(sos.astype(np.float64), x.astype(np.float64))
    got = sos_lib(fixture, api, x)

    peak = float(np.max(np.abs(ref)))
    max_err = float(np.max(np.abs(got - ref)))
    # float32 round-off only; measured ~3e-6 relative, so 1e-4 is ample margin.
    assert max_err <= 1e-4 * peak + 1e-5, (
        f"{fixture}/{api}/{sig_name}: max|c - scipy|={max_err:.3e}, peak={peak:.3e}")
