"""PyQt5 GUI for the filter prepare step.

A thin front-end over tools/prepare.py. Lets the user:
  - open a raw pyfda pole-zero export (.csv/.npy/.npz) -> fields,
  - open an existing canonical <name>.json -> fields,
  - rename the filter, set fs, edit the description (pre-filled template),
  - save the canonical JSON,
  - export a pole-zero CSV from the current state (both directions).

Run:
    python tools/prepare_gui.py
"""
from __future__ import annotations

import signal
import sys
from pathlib import Path

import numpy as np
from PyQt5 import QtWidgets

import prepare as P


class PrepareWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SOS filter - prepare")
        self.resize(640, 560)

        # current numeric filter (set on load)
        self._zeros = np.array([], dtype=complex)
        self._poles = np.array([], dtype=complex)
        self._gain = 1.0

        # --- widgets ---
        self.btn_open_csv = QtWidgets.QPushButton("Open CSV (pole-zero)")
        self.btn_open_json = QtWidgets.QPushButton("Open JSON")
        self.name_edit = QtWidgets.QLineEdit()
        self.fs_edit = QtWidgets.QLineEdit()
        self.fs_edit.setPlaceholderText("e.g. 48000 (optional)")
        self.desc_edit = QtWidgets.QPlainTextEdit()
        self.desc_edit.setPlainText(P.DESCRIPTION_TEMPLATE)

        self.lbl_order = QtWidgets.QLabel("-")
        self.lbl_sections = QtWidgets.QLabel("-")
        self.lbl_gain = QtWidgets.QLabel("-")

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["#", "zero", "pole"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        self.btn_save_json = QtWidgets.QPushButton("Save JSON")
        self.btn_export_csv = QtWidgets.QPushButton("Export pole-zero CSV")
        self.btn_save_json.setEnabled(False)
        self.btn_export_csv.setEnabled(False)

        self.status = QtWidgets.QLabel("Open a pole-zero CSV or a JSON.")

        # --- layout ---
        top = QtWidgets.QHBoxLayout()
        top.addWidget(self.btn_open_csv)
        top.addWidget(self.btn_open_json)
        top.addStretch(1)

        form = QtWidgets.QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("fs [Hz]:", self.fs_edit)
        derived = QtWidgets.QHBoxLayout()
        derived.addWidget(QtWidgets.QLabel("Order:")); derived.addWidget(self.lbl_order)
        derived.addSpacing(16)
        derived.addWidget(QtWidgets.QLabel("Sections:")); derived.addWidget(self.lbl_sections)
        derived.addSpacing(16)
        derived.addWidget(QtWidgets.QLabel("Gain:")); derived.addWidget(self.lbl_gain)
        derived.addStretch(1)
        form.addRow("Derived:", self._wrap(derived))
        form.addRow("Description:", self.desc_edit)

        bottom = QtWidgets.QHBoxLayout()
        bottom.addWidget(self.btn_save_json)
        bottom.addWidget(self.btn_export_csv)
        bottom.addStretch(1)

        root = QtWidgets.QVBoxLayout(self)
        root.addLayout(top)
        root.addLayout(form)
        root.addWidget(QtWidgets.QLabel("Poles and zeros (symmetrized):"))
        root.addWidget(self.table, 1)
        root.addLayout(bottom)
        root.addWidget(self.status)

        # --- signals ---
        self.btn_open_csv.clicked.connect(self.open_csv)
        self.btn_open_json.clicked.connect(self.open_json)
        self.btn_save_json.clicked.connect(self.save_json)
        self.btn_export_csv.clicked.connect(self.export_csv)

    @staticmethod
    def _wrap(layout):
        w = QtWidgets.QWidget()
        w.setLayout(layout)
        return w

    # ----- helpers -----
    def _fs_value(self):
        text = self.fs_edit.text().strip()
        return float(text) if text else None

    def _refresh_from_zpk(self):
        order = len(self._poles)
        from scipy import signal
        try:
            n_sections = signal.zpk2sos(self._zeros, self._poles, self._gain).shape[0]
        except Exception:
            n_sections = (order + 1) // 2
        self.lbl_order.setText(str(order))
        self.lbl_sections.setText(str(n_sections))
        self.lbl_gain.setText(f"{self._gain:g}")

        n = max(len(self._zeros), len(self._poles))
        self.table.setRowCount(n)
        for i in range(n):
            z = f"{self._zeros[i]:.6g}" if i < len(self._zeros) else ""
            p = f"{self._poles[i]:.6g}" if i < len(self._poles) else ""
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(i)))
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(z))
            self.table.setItem(i, 2, QtWidgets.QTableWidgetItem(p))

        ok = order > 0
        self.btn_save_json.setEnabled(ok)
        self.btn_export_csv.setEnabled(ok)

    def _load_spec_into_fields(self, spec):
        self.name_edit.setText(spec.get("name", ""))
        self.fs_edit.setText("" if spec.get("fs") is None else f"{spec['fs']:g}")
        self.desc_edit.setPlainText(spec.get("description") or P.DESCRIPTION_TEMPLATE)
        self._zeros, self._poles, self._gain = P.spec_zpk(spec)
        self._refresh_from_zpk()

    # ----- actions -----
    def open_csv(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open pole-zero export", "", "pyfda export (*.csv *.npy *.npz)")
        if not path:
            return
        try:
            spec = P.csv_to_spec(Path(path), fs=self._fs_value())
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(self, "Error opening CSV", str(exc))
            return
        self._load_spec_into_fields(spec)
        self.status.setText(f"CSV loaded: {Path(path).name} "
                            f"(order {spec['order']}, {spec['n_sections']} sections)")

    def open_json(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open JSON spec", "", "canonical spec (*.json)")
        if not path:
            return
        import json
        try:
            spec = json.loads(Path(path).read_text(encoding="utf-8"))
            self._load_spec_into_fields(spec)
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(self, "Error opening JSON", str(exc))
            return
        self.status.setText(f"JSON loaded: {Path(path).name}")

    def _current_spec(self):
        name = self.name_edit.text().strip() or "filter"
        return P.build_spec(name, self._zeros, self._poles, self._gain,
                            fs=self._fs_value(),
                            description=self.desc_edit.toPlainText())

    def save_json(self):
        name = self.name_edit.text().strip() or "filter"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save JSON spec", f"{name}.json", "canonical spec (*.json)")
        if not path:
            return
        try:
            Path(path).write_text(P.dump_spec(self._current_spec()) + "\n",
                                  encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(self, "Error saving", str(exc))
            return
        self.status.setText(f"JSON saved: {Path(path).name}")

    def export_csv(self):
        name = self.name_edit.text().strip() or "filter"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export pole-zero CSV", f"{name}_polezero.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            Path(path).write_text(P.spec_to_csv_text(self._current_spec()),
                                  encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(self, "Error exporting", str(exc))
            return
        self.status.setText(f"Pole-zero CSV exported: {Path(path).name}")


def main():
    # Let Ctrl+C terminate the Qt event loop cleanly (no traceback dump).
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QtWidgets.QApplication(sys.argv)
    win = PrepareWindow()
    win.show()
    try:
        return app.exec_()
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
