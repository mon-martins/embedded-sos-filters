"""Round-trip test for the prepare tools.

For every pole-zero fixture CSV in tests/data/, verify that
    CSV -> canonical JSON -> CSV
reproduces the original CSV exactly (byte-faithful, modulo newline
normalization). Covers even and odd orders.
"""
import json
from pathlib import Path

import pytest

import prepare as P

DATA = Path(__file__).parent / "data"
CSV_FIXTURES = sorted(DATA.glob("*.csv"))


@pytest.mark.parametrize("csv_path", CSV_FIXTURES, ids=lambda p: p.stem)
def test_csv_json_csv_is_identical(csv_path, tmp_path):
    original = csv_path.read_text(encoding="utf-8")

    # CSV -> canonical spec, persisted to JSON and read back (exercises disk too)
    spec = P.csv_to_spec(csv_path)
    json_path = tmp_path / f"{spec['name']}.json"
    json_path.write_text(P.dump_spec(spec) + "\n", encoding="utf-8")
    spec_back = json.loads(json_path.read_text(encoding="utf-8"))

    # JSON -> CSV
    regenerated = P.spec_to_csv_text(spec_back)

    assert regenerated == original, (
        f"round-trip differs for {csv_path.name}\n"
        f"--- original ---\n{original}\n--- regenerated ---\n{regenerated}"
    )
