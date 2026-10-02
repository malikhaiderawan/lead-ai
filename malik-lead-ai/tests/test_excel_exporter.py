"""Tests for Excel Results Exporter (read-only verification, idempotent, no side effects)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from exporter.excel_exporter import EXCEL_FILENAME, build_excel_workbook, run_export_excel_command

try:
    import openpyxl
except ImportError:
    openpyxl = None


class TestExcelExporter(unittest.TestCase):
    def setUp(self) -> None:
        self.output_dir = Path(__file__).resolve().parent.parent / "output"
        self.excel_file = self.output_dir / EXCEL_FILENAME

    def test_openpyxl_installed(self) -> None:
        self.assertIsNotNone(openpyxl, "openpyxl must be available for Excel exporter tests")

    def test_export_creates_workbook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Copy m5 master csv and send state to tmp
            m5_src = self.output_dir / "malikaxiom_sales_leads.csv"
            st_src = self.output_dir / "m6_send_state.json"
            if m5_src.exists():
                (tmp_path / "malikaxiom_sales_leads.csv").write_bytes(m5_src.read_bytes())
            if st_src.exists():
                (tmp_path / "m6_send_state.json").write_bytes(st_src.read_bytes())

            out_excel = build_excel_workbook(tmp_path, out=lambda *_: None)
            self.assertTrue(out_excel.is_file())
            self.assertGreater(out_excel.stat().st_size, 1000)

    def test_all_expected_sheets_exist(self) -> None:
        if not self.excel_file.exists():
            build_excel_workbook(self.output_dir, out=lambda *_: None)

        wb = openpyxl.load_workbook(self.excel_file, data_only=True)
        expected_sheets = [
            "Summary", "Pipeline", "M1_Raw_Leads", "M2_Research",
            "M3_Qualification", "M4_Outreach", "M5_Decisions",
            "M6_Outreach", "Files_Index",
        ]
        self.assertEqual(wb.sheetnames, expected_sheets)

    def test_pipeline_unique_lead_ids(self) -> None:
        if not self.excel_file.exists():
            build_excel_workbook(self.output_dir, out=lambda *_: None)

        wb = openpyxl.load_workbook(self.excel_file, data_only=True)
        ws_pipe = wb["Pipeline"]
        lead_ids = []
        for r in range(2, ws_pipe.max_row + 1):
            val = ws_pipe.cell(r, 1).value
            if val:
                lead_ids.append(str(val))

        self.assertEqual(len(lead_ids), len(set(lead_ids)), "Pipeline sheet lead_ids must be unique")
        self.assertGreaterEqual(len(lead_ids), 1, "Pipeline should contain leads")

    def test_summary_counts_consistent(self) -> None:
        if not self.excel_file.exists():
            build_excel_workbook(self.output_dir, out=lambda *_: None)

        wb = openpyxl.load_workbook(self.excel_file, data_only=True)
        ws_sum = wb["Summary"]
        metrics = {}
        for r in range(4, ws_sum.max_row + 1):
            name = ws_sum.cell(r, 2).value
            val = ws_sum.cell(r, 3).value
            if name:
                metrics[str(name)] = val

        self.assertIn("Total Unique Master Leads", metrics)
        self.assertIn("M6 Actually SENT", metrics)
        state_file = self.output_dir / "m6_send_state.json"
        if state_file.exists():
            state_data = json.loads(state_file.read_text(encoding="utf-8"))
            expected_sent = sum(1 for v in state_data.get("leads", {}).values() if isinstance(v, dict) and v.get("status") == "SENT")
            self.assertEqual(metrics["M6 Actually SENT"], expected_sent)
        else:
            self.assertGreaterEqual(metrics["M6 Actually SENT"], 0)

    def test_m6_sent_records_represented(self) -> None:
        if not self.excel_file.exists():
            build_excel_workbook(self.output_dir, out=lambda *_: None)

        wb = openpyxl.load_workbook(self.excel_file, data_only=True)
        ws_m6 = wb["M6_Outreach"]

        sent_rows = []
        for r in range(2, ws_m6.max_row + 1):
            status = str(ws_m6.cell(r, 16).value or "")
            if status == "SENT":
                sent_rows.append(ws_m6.cell(r, 1).value)

        self.assertIn("lead_017_arbrandzone", sent_rows)
        self.assertIn("lead_020_branded_clothes_wholesale_in_lahore___za", sent_rows)

    def test_source_files_unmodified(self) -> None:
        state_file = self.output_dir / "m6_send_state.json"
        sales_csv = self.output_dir / "malikaxiom_sales_leads.csv"

        state_before = state_file.read_bytes() if state_file.exists() else None
        csv_before = sales_csv.read_bytes() if sales_csv.exists() else None

        build_excel_workbook(self.output_dir, out=lambda *_: None)

        if state_file.exists():
            self.assertEqual(state_file.read_bytes(), state_before)
        if sales_csv.exists():
            self.assertEqual(sales_csv.read_bytes(), csv_before)

    def test_export_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            m5_src = self.output_dir / "malikaxiom_sales_leads.csv"
            if m5_src.exists():
                (tmp_path / "malikaxiom_sales_leads.csv").write_bytes(m5_src.read_bytes())

            excel_1 = build_excel_workbook(tmp_path, out=lambda *_: None)
            mtime_1 = excel_1.stat().st_mtime

            code = run_export_excel_command(tmp_path, out=lambda *_: None)
            self.assertEqual(code, 0)
            self.assertTrue(excel_1.is_file())

    def test_missing_optional_sources_handled_gracefully(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Empty directory with zero artifacts
            out_excel = build_excel_workbook(tmp_path, out=lambda *_: None)
            self.assertTrue(out_excel.is_file())
            wb = openpyxl.load_workbook(out_excel, data_only=True)
            self.assertIn("Files_Index", wb.sheetnames)

    def test_no_outreach_execution_triggered(self) -> None:
        # Exporter must not invoke playwright or engine channel send
        from m6.send_tracker import SendTracker
        tracker_before = SendTracker(self.output_dir).summary()

        build_excel_workbook(self.output_dir, out=lambda *_: None)

        tracker_after = SendTracker(self.output_dir).summary()
        self.assertEqual(tracker_before, tracker_after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
