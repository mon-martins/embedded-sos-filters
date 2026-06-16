# sos-filter — embedded filter manager

A small, repeatable workflow to take an IIR filter from design to an optimized
embedded **C** implementation, with validation at every step.

Filters are designed in [pyfda](https://github.com/chipmuenk/pyfda), normalized
into a clean canonical spec, converted to **cascaded second-order sections
(SOS)** in **Direct Form II Transposed (DF2T), float32**, validated against
SciPy, and shipped as a portable C runtime plus a generated coefficients
header. A TI C2000 **CLA** variant of the runtime is included.

```
pyfda design  ->  canonical spec  ->  SOS + codegen   ->  validate by sim  ->  C library + tests
  (stage 1)        <name>.json       filters_coeffs.h      plots / report        + golden vectors
```

## Pipeline at a glance

| Stage | Tool | What it does |
|------|------|--------------|
| 1. Design | pyfda | Design the filter; export the pole-zero (zpk) to a CSV/NPY/NPZ. |
| 1.5 Prepare | `tools/prepare.py`, `tools/prepare_gui.py` | Parse the messy pyfda export into a clean canonical `<name>.json` (both directions). |
| 2. Convert / codegen | `tools/convert.py`, `tools/codegen.py` | Scan a folder of specs → one aggregated `filters_coeffs.h` (UPPERCASE `#define` macros). |
| 3. Validate | `tools/validate.py` | Frequency/time/stability/float32 plots + `report.txt` for manual review. |
| 4. C library + tests | `lib/`, `tests/` | DF2T float32 runtime (portable C + CLA), compile tests, golden-vector tests vs SciPy. |

A PyQt5 GUI, `tools/pipeline_gui.py`, ties the stages together (see below).

## Requirements (tools)

External software the project relies on:

| Tool | Version | Needed for |
|------|---------|-----------|
| **Python** | 3.11.x | Everything. pyfda is not yet compatible with 3.14, so stay on 3.11. |
| **uv** | recent | Recommended for creating the venv / installing deps (optional, any pip works). |
| **Docker** | with Compose v2 (tested on 29.x) | Running the test suite and the GUI's "C test plot" button (provides a 64-bit gcc + the Python stack). |
| **C compiler (gcc)** | 64-bit, matching the Python you run | Building the C library / tests **outside** Docker. On Windows use a 64-bit MinGW-w64 — a 32-bit gcc won't load into 64-bit Python. Not needed if you use Docker. |
| **pyfda** | 0.9.5+ | The filter design GUI (installed as a Python dependency; launched from stage 1 / GUI tab 1). |

## Setup

Using [uv](https://github.com/astral-sh/uv):

```sh
uv venv
uv pip install -e ".[dev]"
```

This installs the Python dependencies (pyfda, numpy, scipy, matplotlib, PyQt5;
pytest as a dev extra). The C tests additionally need a C compiler — the
recommended way to run everything is the bundled Docker image (below), which
provides one.

## The GUI

```sh
python tools/pipeline_gui.py
```

Tabs:

1. **Design** — launches pyfda to design and export a filter.
2. **CSV → JSON** — the prepare editor: load a pole-zero export, set name / fs /
   description, save the canonical JSON.
3. **Generate .h** — runs codegen over a folder of specs → `filters_coeffs.h`.
   > The folder is scanned **recursively**, and should contain **only** filter
   > spec JSONs. Non-spec JSON files are ignored with a warning.
4. **C test plot** — builds the C output via Docker and shows it against
   `scipy.sosfilt` in an interactive matplotlib window (zoom / pan / save); a
   PNG is also saved under `build/golden/`.

## Stage details

### 1 — Design (pyfda)
Design the filter and export the **pole-zero (zpk)** to `filters/<name>/`. Use a
lowercase, `_`-separated name so it maps to a valid C identifier.

### 1.5 — Prepare (`tools/prepare.py`)
The pyfda export is "messy" (only zpk, as rounded strings, no metadata). This
stage isolates that and writes one self-contained `<name>.json`:

```sh
python tools/prepare.py csv2json filters/filter_1.csv --fs 48000
python tools/prepare.py json2csv filters/filter_1.json
```

The stored zeros/poles stay byte-faithful to pyfda; conjugate pairs are snapped
to exact symmetry only at conversion time (inside `zpk_to_sos`).

### 2 — Convert / codegen (`tools/convert.py`)
```sh
python tools/convert.py --in filters --out lib/include
```
Produces a single `filters_coeffs.h` with, per filter, UPPERCASE `#define`
macros only — no init functions, no `static` arrays:

```c
#define FILTER_SOS_<NAME>_N_SECTIONS 2
#define FILTER_SOS_<NAME>_COEFFS { \
    b0, b1, b2, a1, a2,  /* section 0 */ \
    b0, b1, b2, a1, a2   /* section 1 */ }
#define FILTER_SOS_<NAME>_ORDER 4
/* ...GAIN, FS, ... */
```

### 3 — Validate (`tools/validate.py`)
```sh
python tools/validate.py filters/filter_1.json --out build/validation
```
Writes four diagrams (frequency response, time vs `scipy.sosfilt`, pole-zero,
float32 error) plus `report.txt` for manual confirmation.

### 4 — C library (`lib/`)
DF2T, float32, no dynamic allocation — the caller owns the coefficient and
state buffers.

- `lib/include/sos_filter.h` + `lib/source_c/sos_filter.c` — portable C.
- `lib/include/sos_filter_cla.h` + `lib/source_cla/sos_filter_cla.cla` — TI
  C2000 CLA variant (build with `cl2000 --cla_support`).

Coefficient layout, denominator normalized (`a0 = 1`), 5 values per section:
`b0, b1, b2, a1, a2`. State (DF2T): 2 delay vars per section. Odd-order filters
are handled with no special case (a 1st-order section is `b0, b1, 0, a1, 0`).

Pair the generated header with the runtime in your own code:

```c
#include "sos_filter.h"
#include "filters_coeffs.h"

static const float32_t coeffs[] = FILTER_SOS_MY_FILTER_COEFFS;
static float32_t state[2 * FILTER_SOS_MY_FILTER_N_SECTIONS];

sos_filt_t f;
sos_init(&f, coeffs, state, FILTER_SOS_MY_FILTER_N_SECTIONS);
sos_process_block(&f, in, out, n);   /* or sos_process(&f, x) per sample */
```

## Tests

The suite runs in a pinned Docker image (Python + deps + a 64-bit gcc), the same
environment used in CI:

```sh
docker compose run --rm tests
```

It covers the conversion pipeline, header generation, C compile checks, and
**golden-vector** tests that compile the C library and compare its float32
output to `scipy.sosfilt`. Tests that build the C library skip gracefully if no
suitable compiler is available, so plain `pytest` also works where a 64-bit gcc
is on `PATH`.

CI runs the same command on `ubuntu-latest` (`.github/workflows/tests.yml`).

## Repository layout

```
sos_filter/
├── tools/            # pipeline stages + GUIs
│   ├── prepare.py / prepare_gui.py
│   ├── convert.py / codegen.py
│   ├── validate.py
│   ├── plot_golden.py        # C output vs scipy (used by the GUI)
│   └── pipeline_gui.py       # stage manager (PyQt5)
├── lib/
│   ├── include/              # sos_filter.h, sos_filter_cla.h
│   ├── source_c/             # sos_filter.c
│   └── source_cla/           # sos_filter_cla.cla
├── tests/                    # pytest suite (+ tests/apply/ wrappers, tests/data/ fixtures)
├── filters/                  # designed filters (gitignored; not versioned)
├── Dockerfile / docker-compose.yml
└── .github/workflows/tests.yml
```

`filters/` and the generated `lib/include/filters_coeffs.h` are gitignored
(build artifacts / local designs).

## Licensing

See [`LICENSING.md`](LICENSING.md) and [`LICENSE`](LICENSE); the runtime library
under `lib/` carries its own [`lib/LICENSE`](lib/LICENSE).
