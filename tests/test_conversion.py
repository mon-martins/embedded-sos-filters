"""Conversion validation: the SOS cascade must match the direct (b,a) form.

For every pole-zero fixture, build the SOS via zpk_to_sos and the plain
direct-form transfer function from the same (symmetrized) zpk, then assert
their frequency responses agree. This checks that converting zpk -> SOS does
not distort the filter (covers even and odd orders).

Purely in-memory -- file writing is validated elsewhere.
"""
from pathlib import Path

import numpy as np
import pytest
from scipy import signal

import prepare as P

DATA = Path(__file__).parent / "data"
CSV_FIXTURES = sorted(DATA.glob("*.csv"))


@pytest.mark.parametrize("csv_path", CSV_FIXTURES, ids=lambda p: p.stem)
def test_sos_matches_direct_response(csv_path):
    spec = P.csv_to_spec(csv_path)
    z, p, k = P.spec_zpk(spec)

    sos = P.zpk_to_sos(z, p, k)                                   # our conversion
    b, a = signal.zpk2tf(P.symmetrize(z), P.symmetrize(p), k)     # direct form

    w_sos, h_sos = signal.sosfreqz(sos, worN=4096)
    w_dir, h_dir = signal.freqz(b, a, worN=4096)

    # Same frequency grid -> compare the complex responses point by point.
    assert np.max(np.abs(h_sos - h_dir)) < 1e-4
