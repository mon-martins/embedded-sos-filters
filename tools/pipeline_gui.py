"""PyQt5 GUI to drive the SOS-filter pipeline stages.

Tabs:
  1. Design        -- launch pyfda to design/export a filter.
  2. CSV -> JSON    -- the prepare editor (load CSV, edit metadata, save JSON).
  3. Generate .h    -- run codegen over a specs folder -> filters_coeffs.h.
  4. C test plot    -- build the C output via Docker, then show it vs scipy in
                       an interactive matplotlib window (zoom/pan/save).

Each action picks its file/folder on demand (no fixed working directory).

Run:
    python tools/pipeline_gui.py
"""
from __future__ import annotations

import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PyQt5 import QtCore, QtWidgets

sys.path.insert(0, str(Path(__file__).resolve().parent))
import convert as C  # noqa: E402
from prepare_gui import PrepareWindow  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_H = ROOT / "lib" / "include"
PLOT_OUT = ROOT / "build" / "golden"


def _open_path(path: Path) -> None:
    """Open a file or folder with the host's default handler."""
    if platform.system() == "Windows":
        os.startfile(str(path))  # noqa: S606
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


class PlotDialog(QtWidgets.QDialog):
    """Interactive matplotlib window (with the navigation toolbar) for results.

    `results` maps a signal name to (ref, got) arrays. Embeds a FigureCanvas so
    zoom/pan/save work, without touching the host's default matplotlib backend.
    """
    def __init__(self, title, results, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1000, 760)

        from matplotlib.backends.backend_qt5agg import (
            FigureCanvasQTAgg, NavigationToolbar2QT)
        from matplotlib.figure import Figure

        fig = Figure(figsize=(12, 8))
        canvas = FigureCanvasQTAgg(fig)
        toolbar = NavigationToolbar2QT(canvas, self)
        axes = fig.subplots(len(results), 2, squeeze=False)
        for row, (name, (ref, got)) in enumerate(results.items()):
            err = got - ref
            ax_o, ax_e = axes[row]
            ax_o.plot(ref, color="C1", lw=1.4, label="scipy.sosfilt (ref)")
            ax_o.plot(got, color="C0", lw=0.8, ls="--", label="C output (float32)")
            ax_o.set_ylabel(name); ax_o.grid(True); ax_o.legend(loc="upper right", fontsize=8)
            ax_e.plot(err, color="C3", lw=0.8)
            ax_e.set_ylabel(f"error\nmax={np.max(np.abs(err)):.2e}"); ax_e.grid(True)
        axes[0, 0].set_title("C output vs scipy")
        axes[0, 1].set_title("error (C - scipy)")
        fig.tight_layout()

        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(toolbar)
        lay.addWidget(canvas)


class PipelineWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SOS filter - pipeline")
        self.resize(720, 640)

        self._proc: QtCore.QProcess | None = None  # Docker plot job
        self._job_tmp: Path | None = None          # per-job temp dir under build/
        self._plot_windows: list = []              # keep dialogs from being GC'd

        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self._tab_design(), "1. Design")
        tabs.addTab(PrepareWindow(), "2. CSV -> JSON")
        tabs.addTab(self._tab_header(), "3. Generate .h")
        tabs.addTab(self._tab_plot(), "4. C test plot")
        self.setCentralWidget(tabs)

    # ----- tab 1: design -----
    def _tab_design(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.addWidget(QtWidgets.QLabel(
            "Design a filter in pyfda and export the pole-zero (zpk) to filters/."))
        btn = QtWidgets.QPushButton("Open pyfda")
        btn.clicked.connect(self._open_pyfda)
        lay.addWidget(btn)
        self.design_status = QtWidgets.QLabel("")
        lay.addWidget(self.design_status)
        lay.addStretch(1)
        return w

    def _open_pyfda(self) -> None:
        try:
            subprocess.Popen([sys.executable, "-m", "pyfda.pyfdax"])
            self.design_status.setText("pyfda launched.")
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(self, "Error launching pyfda", str(exc))

    # ----- tab 3: generate header -----
    def _tab_header(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.addWidget(QtWidgets.QLabel(
            "Generate filters_coeffs.h from a folder of canonical JSON specs.\n"
            "The folder is scanned recursively; non-spec JSON files are ignored "
            "with a warning."))

        self.in_dir_edit = QtWidgets.QLineEdit(str(ROOT / "filters"))
        self.out_dir_edit = QtWidgets.QLineEdit(str(DEFAULT_OUT_H))
        lay.addLayout(self._row("Specs folder:", self.in_dir_edit, self._pick_in_dir))
        lay.addLayout(self._row("Output folder:", self.out_dir_edit, self._pick_out_dir))

        btns = QtWidgets.QHBoxLayout()
        gen = QtWidgets.QPushButton("Generate .h")
        gen.clicked.connect(self._generate_header)
        self.btn_open_h = QtWidgets.QPushButton("Open header")
        self.btn_open_h.setEnabled(False)
        self.btn_open_h.clicked.connect(
            lambda: _open_path(Path(self.out_dir_edit.text()) / "filters_coeffs.h"))
        btns.addWidget(gen); btns.addWidget(self.btn_open_h); btns.addStretch(1)
        lay.addLayout(btns)

        self.header_status = QtWidgets.QLabel("")
        self.header_status.setWordWrap(True)
        lay.addWidget(self.header_status)
        lay.addStretch(1)
        return w

    def _generate_header(self) -> None:
        in_dir, out_dir = self.in_dir_edit.text().strip(), self.out_dir_edit.text().strip()
        if not Path(in_dir).is_dir():
            QtWidgets.QMessageBox.warning(self, "Generate .h", f"Not a folder: {in_dir}")
            return
        try:
            rc = C.main(["--in", in_dir, "--out", out_dir])
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(self, "Generate .h failed", str(exc))
            return
        if rc != 0:
            self.header_status.setText(f"No specs found under {in_dir} (nothing written).")
            return
        self.header_status.setText(
            f"Wrote {out_dir}/filters_coeffs.h")
        self.btn_open_h.setEnabled(True)

    # ----- tab 4: C test plot (via Docker) -----
    def _tab_plot(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.addWidget(QtWidgets.QLabel(
            "Plot the C-library output vs scipy.sosfilt for a spec, built via Docker."))

        self.plot_spec_edit = QtWidgets.QLineEdit()
        self.plot_spec_edit.setPlaceholderText("pick a pole-zero CSV or JSON spec")
        lay.addLayout(self._row("Spec:", self.plot_spec_edit, self._pick_spec))

        btns = QtWidgets.QHBoxLayout()
        self.btn_gen_plot = QtWidgets.QPushButton("Generate && show (Docker)")
        self.btn_gen_plot.clicked.connect(self._generate_plot)
        self.btn_open_plot = QtWidgets.QPushButton("Open PNG folder")
        self.btn_open_plot.clicked.connect(lambda: _open_path(PLOT_OUT))
        btns.addWidget(self.btn_gen_plot); btns.addWidget(self.btn_open_plot); btns.addStretch(1)
        lay.addLayout(btns)

        self.plot_log = QtWidgets.QPlainTextEdit()
        self.plot_log.setReadOnly(True)
        lay.addWidget(self.plot_log, 1)
        return w

    def _generate_plot(self) -> None:
        spec = self.plot_spec_edit.text().strip()
        if not spec or not Path(spec).is_file():
            QtWidgets.QMessageBox.warning(self, "C test plot", "Pick an existing spec file.")
            return
        if self._proc is not None:
            QtWidgets.QMessageBox.information(self, "C test plot", "A job is already running.")
            return

        # Per-job temp dir under build/ (mounted into the container, deleted when
        # the job finishes). Holds the .npz of raw arrays the host plots, plus a
        # copy of the spec if it lives outside the repo (so the container sees it).
        (ROOT / "build").mkdir(exist_ok=True)
        self._job_tmp = Path(tempfile.mkdtemp(dir=str(ROOT / "build"), prefix="_plot_"))
        src = Path(spec).resolve()
        try:
            rel = src.relative_to(ROOT)
        except ValueError:
            rel = Path(shutil.copy(src, self._job_tmp / src.name)).relative_to(ROOT)
        npz_rel = self._job_tmp.relative_to(ROOT)

        cmd = ["compose", "run", "--rm", "tests", "python", "tools/plot_golden.py",
               rel.as_posix(), "--out", "build/golden", "--npz", npz_rel.as_posix()]
        self.plot_log.clear()
        self.plot_log.appendPlainText("$ docker " + " ".join(cmd) + "\n")
        self.btn_gen_plot.setEnabled(False)

        proc = QtCore.QProcess(self)
        proc.setWorkingDirectory(str(ROOT))
        proc.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        proc.readyReadStandardOutput.connect(
            lambda: self.plot_log.appendPlainText(
                bytes(proc.readAllStandardOutput()).decode(errors="replace").rstrip()))
        proc.finished.connect(self._plot_finished)
        proc.errorOccurred.connect(
            lambda _e: self.plot_log.appendPlainText(f"[error] {proc.errorString()}"))
        self._proc = proc
        proc.start("docker", cmd)

    def _plot_finished(self, code, _status) -> None:
        self.plot_log.appendPlainText(f"\n[done] exit code {code}")
        if code == 0 and self._job_tmp is not None:
            for npz in sorted(self._job_tmp.glob("*.npz")):
                try:
                    self._open_interactive(npz)
                except Exception as exc:  # noqa: BLE001
                    self.plot_log.appendPlainText(f"[warn] could not open {npz.name}: {exc}")
            self.plot_log.appendPlainText(f"Interactive window opened; PNGs in {PLOT_OUT}")
        # Drop the per-job temp dir (arrays are already loaded into the window).
        if self._job_tmp is not None:
            shutil.rmtree(self._job_tmp, ignore_errors=True)
            self._job_tmp = None
        self.btn_gen_plot.setEnabled(True)
        self._proc = None

    def _open_interactive(self, npz_path: Path) -> None:
        data = np.load(npz_path)
        names = [str(n) for n in data["_signal_names"]]
        results = {n: (data[f"{n}_ref"], data[f"{n}_got"]) for n in names}
        dlg = PlotDialog(f"{data['filter_name']} - C output vs scipy", results, self)
        self._plot_windows.append(dlg)
        dlg.show()

    # ----- shared helpers -----
    def _row(self, label, edit, on_browse):
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel(label))
        row.addWidget(edit, 1)
        btn = QtWidgets.QPushButton("Browse...")
        btn.clicked.connect(on_browse)
        row.addWidget(btn)
        return row

    def _pick_in_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Specs folder", self.in_dir_edit.text())
        if d:
            self.in_dir_edit.setText(d)

    def _pick_out_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Output folder", self.out_dir_edit.text())
        if d:
            self.out_dir_edit.setText(d)

    def _pick_spec(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Pick spec", str(ROOT / "filters"),
            "filter spec (*.json *.csv *.npy *.npz)")
        if path:
            self.plot_spec_edit.setText(path)


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QtWidgets.QApplication(sys.argv)
    win = PipelineWindow()
    win.show()
    try:
        return app.exec_()
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
