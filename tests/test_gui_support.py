import unittest
from pathlib import Path

from dlss5_enhance.logging_setup import ProgressLine
from dlss5_enhance.media import exceeds_limits, raw_scaled_size
from dlss5_enhance.report import (
    STATUS_CANCELLED,
    STATUS_FAILED,
    STATUS_NEW,
    JobResult,
    counts,
    exit_code,
)
from dlss5_enhance.sink import CollectSink, ConsoleSink, QueueSink


class GeometryLimitTests(unittest.TestCase):
    def test_1080p_at_3x_is_fine(self):
        self.assertIsNone(exceeds_limits(1920, 1080, 3.0))

    def test_1080p_at_4x_is_exactly_at_the_cap(self):
        self.assertIsNone(exceeds_limits(1920, 1080, 4.0))

    def test_1080p_at_5x_is_refused(self):
        self.assertIsNotNone(exceeds_limits(1920, 1080, 5.0))

    def test_8k_source_at_2x_is_refused_before_the_node(self):
        self.assertIsNotNone(exceeds_limits(7680, 4320, 2.0))

    def test_raw_scaled_size(self):
        self.assertEqual(raw_scaled_size(480, 270, 3.0), (1440, 810))


class CancelledExitCodeTests(unittest.TestCase):
    def test_cancel_returns_130(self):
        results = [
            JobResult(source=Path("a.mp4"), status=STATUS_NEW, output=Path("a_x.mkv")),
            JobResult(source=Path("b.mp4"), status=STATUS_CANCELLED, reason="annulé"),
        ]
        self.assertEqual(exit_code(results), 130)

    def test_plain_failure_returns_1(self):
        results = [JobResult(source=Path("a.mp4"), status=STATUS_FAILED, reason="boum")]
        self.assertEqual(exit_code(results), 1)

    def test_cancelled_counts_as_failure_in_the_summary(self):
        stats = counts([JobResult(source=Path("a.mp4"), status=STATUS_CANCELLED)])
        self.assertEqual(stats["failed"], 1)


class SinkTests(unittest.TestCase):
    def test_collect_sink(self):
        sink = CollectSink()
        sink.line("bonjour")
        sink.progress("50%")
        sink.clear()
        self.assertEqual(sink.lines, ["bonjour"])
        self.assertEqual(sink.progress_text, "50%")
        self.assertEqual(sink.cleared, 1)
        self.assertFalse(sink.interactive)

    def test_queue_sink_posts_messages(self):
        import queue

        messages: queue.Queue = queue.Queue()
        sink = QueueSink(messages)
        sink.line("a")
        sink.progress("b")
        sink.clear()
        sink.finished(0)
        kinds = [messages.get_nowait()[0] for _ in range(4)]
        self.assertEqual(kinds, ["line", "progress", "clear", "done"])
        self.assertTrue(sink.interactive)

    def test_console_sink_writes_lines(self):
        import io

        stream = io.StringIO()
        sink = ConsoleSink(ProgressLine(stream=stream, enabled=False), stream=stream)
        sink.line("hello")
        sink.progress("ignored")
        self.assertIn("hello", stream.getvalue())
        self.assertFalse(sink.interactive)


if __name__ == "__main__":
    unittest.main()
