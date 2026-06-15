"""Compile-check the C library sources.

The library headers include no standard header and do not typedef the scalar
types -- float32_t and the integer types come from the MCU library / build.
For the host tests we force-include a per-target stand-in that provides those
types (tests/data/c28x_types.h, tests/data/cla_types.h), mirroring how the
real device headers would.

Skipped when no host C compiler is available; the CI runner has one.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INC = ROOT / "lib" / "include"
DATA = Path(__file__).parent / "data"
SRC_C = ROOT / "lib" / "source_c" / "sos_filter.c"
SRC_CLA = ROOT / "lib" / "source_cla" / "sos_filter_cla.cla"

_CC = next((c for c in ("cc", "gcc", "clang") if shutil.which(c)), None)

pytestmark = pytest.mark.skipif(_CC is None, reason="no C compiler (cc/gcc/clang)")


def _run(types_header, extra):
    return subprocess.run(
        [_CC, "-std=c99", "-Wall", "-Wextra",
         "-include", str(DATA / types_header), "-I", str(INC), *extra],
        capture_output=True, text=True)


def test_source_c_compiles(tmp_path):
    r = _run("c28x_types.h", ["-c", str(SRC_C), "-o", str(tmp_path / "sos_filter.o")])
    assert r.returncode == 0, r.stderr


def test_source_cla_compiles():
    # CLA C is a subset of C; syntax-check the algorithm with the host compiler
    # (a real build needs the TI cl2000 compiler with --cla_support).
    r = _run("cla_types.h", ["-x", "c", "-fsyntax-only", str(SRC_CLA)])
    assert r.returncode == 0, r.stderr
