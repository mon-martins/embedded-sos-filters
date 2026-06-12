"""Validate the validation tool: it must produce all plots + the report.

Runs validate on a known fixture (filter_order4) and checks every expected
output file is generated and non-empty.
"""
from pathlib import Path

import validate as V

DATA = Path(__file__).parent / "data"

EXPECTED = [
    "01_frequency_response.png",
    "02_time_vs_reference.png",
    "03_pole_zero.png",
    "04_float32_error.png",
    "report.txt",
]


def test_validate_generates_all_outputs(tmp_path):
    assert V.main([str(DATA / "filter_order4.csv"), "--out", str(tmp_path)]) == 0

    outdir = tmp_path / "filter_order4"
    for name in EXPECTED:
        f = outdir / name
        assert f.exists() and f.stat().st_size > 0, f"missing/empty: {name}"
