from __future__ import annotations

import unittest

from mini_drop.perf_importer import parse_perf_script


class PerfImporterTest(unittest.TestCase):
    def test_parse_perf_script_groups_indented_symbol_stacks(self) -> None:
        text = """
python 1234 111.111: cycles:
        7fffaaa runtime_eval
        7fffbbb handle_request
        7fffccc hot_loop

python 1234 112.111: cycles:
        7fffaaa runtime_eval
        7fffddd flush_metrics
"""
        samples = parse_perf_script(text)
        self.assertEqual(len(samples), 2)
        self.assertEqual(samples[0]["source"], "perf-script-import")
        self.assertEqual(samples[0]["pid"], 1234)
        self.assertEqual(samples[0]["stack"], ["runtime_eval", "handle_request", "hot_loop"])
        self.assertEqual(samples[1]["stack"], ["runtime_eval", "flush_metrics"])


if __name__ == "__main__":
    unittest.main()
