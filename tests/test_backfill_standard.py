from __future__ import annotations

import unittest

from scripts import backfill_standard as bs


class BackfillStandardTests(unittest.TestCase):
    def test_committed_runs_match_the_script(self) -> None:
        # Recomputes golden numbers from t2/ raw evidence (fails on a mismatch with the
        # published values) and compares with the committed runs/*.
        self.assertEqual(bs.main(["--check"]), 0)

    def test_tier2_rows_cover_every_test_once_per_subject(self) -> None:
        for fn in bs.RUNS[1:]:
            manifest, rows = fn()
            for subject in manifest["subjects"]:
                ids = [r["sample_id"] for r in rows if r["subject"] == subject["name"]]
                self.assertEqual(ids, bs.TESTS + ["golden"], manifest["id"])

    def test_fx_and_nanocodex_are_custom_setups(self) -> None:
        by_id = {m["id"]: m for m, _ in (fn() for fn in bs.RUNS)}
        for run_id in ("2026-09-17-tier2-fx-grok", "2026-10-04-tier2-nanocodex-mimo"):
            self.assertEqual(by_id[run_id]["setup"], "custom")
            self.assertEqual(by_id[run_id]["comparisons"], [])


if __name__ == "__main__":
    unittest.main()
