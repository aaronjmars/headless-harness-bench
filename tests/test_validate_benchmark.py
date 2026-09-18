from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_benchmark import HARNESSES, validate


class ValidateBenchmarkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "README.md").write_text("benchmark", encoding="utf-8")
        (self.root / "BENCHMARK.md").write_text("details", encoding="utf-8")
        complete_report = "\n".join(
            [f"| T{number} | PASS |" for number in range(1, 9)]
            + ["TASK SUCCESS: PASS"]
        )
        for harness in HARNESSES:
            directory = self.root / "t2" / harness
            directory.mkdir(parents=True)
            (directory / "RESULT.md").write_text(complete_report, encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_complete_benchmark_passes(self) -> None:
        evidence = self.root / "t2" / "omp" / "events.jsonl"
        evidence.write_text(json.dumps({"type": "done"}) + "\n", encoding="utf-8")
        self.assertEqual(validate(self.root), [])

    def test_empty_failure_capture_is_allowed(self) -> None:
        (self.root / "t2" / "pi" / "startup.jsonl").touch()
        self.assertEqual(validate(self.root), [])

    def test_invalid_jsonl_reports_the_line(self) -> None:
        evidence = self.root / "t2" / "dsh" / "events.jsonl"
        evidence.write_text('{"ok": true}\nnot-json\n', encoding="utf-8")
        self.assertTrue(any("events.jsonl:2" in error for error in validate(self.root)))

    def test_missing_test_result_is_rejected(self) -> None:
        report = self.root / "t2" / "fx" / "RESULT.md"
        report.write_text("T1 T2 T3 T4 T5 T6 T7\nTASK SUCCESS", encoding="utf-8")
        self.assertTrue(any("missing T8" in error for error in validate(self.root)))

    def test_token_only_results_and_task_success_are_rejected(self) -> None:
        report = self.root / "t2" / "fx" / "RESULT.md"
        report.write_text(
            "T1 T2 T3 T4 T5 T6 T7 T8\nTASK SUCCESS",
            encoding="utf-8",
        )
        errors = validate(self.root)
        for test_number in range(1, 9):
            self.assertTrue(
                any(f"missing T{test_number} result value" in error for error in errors)
            )
        self.assertTrue(any("missing task-success verdict" in error for error in errors))

    def test_empty_result_cells_are_rejected(self) -> None:
        report = self.root / "t2" / "fx" / "RESULT.md"
        report.write_text(
            "\n".join([f"| T{number} | |" for number in range(1, 9)])
            + "\n| TASK SUCCESS | |",
            encoding="utf-8",
        )
        errors = validate(self.root)
        self.assertEqual(len(errors), 9)

    def test_credential_shaped_artifact_is_rejected(self) -> None:
        (self.root / "t2" / "crush" / "auth.json").write_text("{}", encoding="utf-8")
        self.assertTrue(any("credential-shaped" in error for error in validate(self.root)))

    def test_credential_shaped_artifact_is_case_insensitive(self) -> None:
        (self.root / "t2" / "crush" / ".ENV.production").write_text(
            "SECRET=value", encoding="utf-8"
        )
        self.assertTrue(any("credential-shaped" in error for error in validate(self.root)))


if __name__ == "__main__":
    unittest.main()
