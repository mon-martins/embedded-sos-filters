"""Generate the aggregated C header from the filters and compile it.

1. From each CSV fixture, generate its JSON spec, then convert the specs ->
   filters_coeffs.h                                          (test 1: generated)
2. Compile a main.c that only includes the header            (test 2: valid C)

The JSON specs are generated on the fly (not committed) so they never go stale.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

import convert as C
import prepare as P

DATA = Path(__file__).parent / "data"
CSV_FIXTURES = sorted(DATA.glob("*.csv"))
_CC = next((c for c in ("cc", "gcc", "clang") if shutil.which(c)), None)


@pytest.fixture(scope="module")
def header(tmp_path_factory):
    base = tmp_path_factory.mktemp("stage2")
    specs = base / "specs"
    specs.mkdir()
    for csv in CSV_FIXTURES:
        spec = P.csv_to_spec(csv)
        (specs / f"{spec['name']}.json").write_text(
            P.dump_spec(spec) + "\n", encoding="utf-8")

    out = base / "include"
    assert C.main(["--in", str(specs), "--out", str(out)]) == 0
    return out / "filters_coeffs.h"


def test_header_generated(header):
    assert header.exists() and header.stat().st_size > 0


@pytest.mark.skipif(_CC is None, reason="no C compiler (cc/gcc/clang) available")
def test_header_compiles(header, tmp_path):
    main_c = tmp_path / "main.c"
    main_c.write_text('#include "filters_coeffs.h"\nint main(void) { return 0; }\n',
                      encoding="utf-8")
    result = subprocess.run(
        [_CC, str(main_c), "-o", str(tmp_path / "a.out"), "-I", str(header.parent)],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
