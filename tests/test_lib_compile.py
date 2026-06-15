"""Compile-check the C library sources.

The library headers include no standard header and do not typedef the scalar
types -- float32_t and the integer types come from the MCU library / build.
So we supply them on the compile command (-include stdint.h/stddef.h,
-Dfloat32_t=float), mirroring how a target build provides its device types.

Skipped when no host C compiler is available; the CI runner (and TI builds on
the target) have one.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INC = ROOT / "lib" / "include"
SRC_C = ROOT / "lib" / "source_c" / "sos_filter.c"
SRC_CLA = ROOT / "lib" / "source_cla" / "sos_filter_cla.cla"

_CC = next((c for c in ("cc", "gcc", "clang") if shutil.which(c)), None)

# Scalar types supplied by the build (stand-in for the MCU library headers).
PROVIDE = ["-include", "stdint.h", "-include", "stddef.h", "-Dfloat32_t=float"]

pytestmark = pytest.mark.skipif(_CC is None, reason="no C compiler (cc/gcc/clang)")


def _run(extra):
    return subprocess.run(
        [_CC, "-std=c99", "-Wall", "-Wextra", *PROVIDE, "-I", str(INC), *extra],
        capture_output=True, text=True)


def test_source_c_compiles(tmp_path):
    r = _run(["-c", str(SRC_C), "-o", str(tmp_path / "sos_filter.o")])
    assert r.returncode == 0, r.stderr


def test_source_cla_compiles():
    # CLA C is a subset of C; syntax-check the algorithm with the host compiler
    # (a real build needs the TI cl2000 compiler with --cla_support).
    r = _run(["-x", "c", "-fsyntax-only", str(SRC_CLA)])
    assert r.returncode == 0, r.stderr
