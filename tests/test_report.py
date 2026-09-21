import unittest
from pathlib import Path

from dlss5_enhance.report import (
    STATUS_CACHE,
    STATUS_CRASHED,
    STATUS_NEW,
    STATUS_TIMEOUT,
    JobResult,
    counts,
    exit_code,
    format_result_line,
    format_summary,
)


def results():
    return [
        JobResult(source=Path("a.mp4"), status=STATUS_NEW, output=Path("out/a_x.mkv"), seconds=42),
        JobResult(source=Path("b.mp4"), status=STATUS_CACHE, output=Path("out/b_y.mkv"), seconds=3),
        JobResult(
            source=Path("c.mp4"),
            status=STATUS_TIMEOUT,
            reason="timeout après 1200 s",
            seconds=1200,
        ),
    ]


class CounterTests(unittest.TestCase):
    def test_three_counters_are_separate(self):
        stats = counts(results())
        self.assertEqual(stats, {"total": 3, "new": 1, "cache": 1, "failed": 1})

    def test_exit_code_non_zero_when_a_job_failed(self):
        self.assertEqual(exit_code(results()), 1)

    def test_exit_code_zero_when_cache_hits_only(self):
        only_ok = [item for item in results() if not item.failed]
        self.assertEqual(exit_code(only_ok), 0)


class SummaryTests(unittest.TestCase):
    def test_summary_counts_and_failures(self):
        lines = format_summary(results())
        text = "\n".join(lines)
        self.assertIn("3 file(s)", text)
        self.assertIn("1 new render(s)", text)
        self.assertIn("1 served from cache", text)
        self.assertIn("1 failure(s)", text)
        self.assertIn("c.mp4", text)
        self.assertIn("timeout", text)

    def test_summary_without_failures_has_no_failure_block(self):
        lines = format_summary([item for item in results() if not item.failed])
        self.assertNotIn("Failures:", "\n".join(lines))

    def test_crashed_job_is_listed(self):
        crashed = JobResult(
            source=Path("d.mp4"),
            status=STATUS_CRASHED,
            reason="serveur ComfyUI mort",
        )
        text = "\n".join(format_summary([crashed]))
        self.assertIn("d.mp4", text)
        self.assertIn("serveur ComfyUI mort", text)


class ResultLineTests(unittest.TestCase):
    def test_cache_hit_is_never_reported_as_a_new_render(self):
        line = format_result_line(
            JobResult(
                source=Path("b.mp4"),
                status=STATUS_CACHE,
                output=Path("out/b_y.mkv"),
                seconds=3,
                cached_signal=True,
            )
        )
        self.assertIn("CACHE-HIT", line)
        self.assertIn("no new render", line)
        self.assertIn("--force", line)
        self.assertIn("out", line)
        self.assertNotIn("OK —", line)

    def test_new_render_line_points_at_the_output(self):
        line = format_result_line(results()[0])
        self.assertIn("new render", line)
        self.assertIn("a_x.mkv", line)

    def test_failure_line_carries_the_reason(self):
        line = format_result_line(results()[2])
        self.assertIn("TIMEOUT", line)
        self.assertIn("1200", line)


if __name__ == "__main__":
    unittest.main()
