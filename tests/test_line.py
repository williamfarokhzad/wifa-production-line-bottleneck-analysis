import json
from pathlib import Path
import random
import subprocess
import sys
import unittest

from line import simulate


def config(cycles, seconds, buffers, pauses=()):
    return {
        "stations": [[chr(65 + i), v] for i, v in enumerate(cycles)],
        "seconds": seconds, "buffers": buffers, "pauses": list(pauses),
    }


def completion_oracle(cycles, horizon, zero_buffers):
    """Job-by-job departure recurrence; independent of the one-second simulator."""
    previous = [0] * len(cycles)
    output = []
    while True:
        departure = []
        for i, duration in enumerate(cycles):
            arrival = departure[-1] if i else 0
            process_end = max(arrival, previous[i]) + duration
            # With direct handoff, the receiving station must release its prior job.
            next_free = previous[i + 1] if zero_buffers and i + 1 < len(cycles) else 0
            departure.append(max(process_end, next_free))
        if departure[-1] > horizon:
            return output
        output.append(departure[-1])
        previous = departure


class TestLine(unittest.TestCase):
    def test_hand_timed_first_part_and_cadence(self):
        r = simulate(config([5, 8, 6], 35, [1, 1]))
        self.assertEqual(r["completion_times_s"], [19, 27, 35])
        self.assertEqual(r["observed_parts_per_hour"], round(3 * 3600 / 35, 3))

    def test_equal_cycle_handoff_does_not_add_fake_delay(self):
        r = simulate(config([2, 2, 2], 10, [0, 0]))
        self.assertEqual(r["completion_times_s"], [6, 8, 10])
        self.assertEqual(r["peak_waiting_parts"], [0, 0])

    def test_unfinished_before_first_delivery(self):
        r = simulate(config([4, 7], 4, [0]))
        self.assertEqual((r["admitted"], r["completed"], r["unfinished"]), (1, 0, 1))

    def test_pause_resumes_remaining_work_and_preserves_buffer_limit(self):
        paused = [["B", 3, 6]]
        r = simulate(config([2, 4], 9, [0], paused))
        self.assertEqual(r["completion_times_s"], [9])
        self.assertEqual(r["station_seconds"]["B"]["offline"], 3)
        self.assertEqual(r["station_seconds"]["A"]["blocked"], 5)
        self.assertEqual(r["peak_waiting_parts"], [0])

    def test_no_progress_with_sink_offline_entire_window(self):
        r = simulate(config([2, 2], 10, [1], [["B", 0, 10]]))
        self.assertEqual((r["completed"], r["unfinished"], r["peak_waiting_parts"]), (0, 2, [1]))
        self.assertEqual(r["station_seconds"]["A"]["blocked"], 6)

    def test_capacity_and_conservation_across_pause_offsets(self):
        for start in range(10):
            for cap in range(4):
                with self.subTest(start=start, cap=cap):
                    r = simulate(config([2, 3, 2], 30, [1, cap], [["B", start, start + 3]]))
                    self.assertEqual(r["admitted"], r["completed"] + r["unfinished"])
                    self.assertTrue(all(sum(x.values()) == 30 for x in r["station_seconds"].values()))
                    self.assertLessEqual(r["completed"], r["isolated_completion_upper_bound"])
                    self.assertLessEqual(r["peak_waiting_parts"][1], cap)

    def test_oracle_across_120_seeded_topologies(self):
        rng = random.Random(435)
        for i in range(120):
            cycles = [rng.randint(1, 12) for _ in range(rng.randint(2, 7))]
            horizon = rng.randint(10, 70)
            for slots in (0, horizon):
                with self.subTest(i=i, slots=slots):
                    r = simulate(config(cycles, horizon, [slots] * (len(cycles) - 1)))
                    self.assertEqual(r["completion_times_s"], completion_oracle(cycles, horizon, slots == 0))

    def test_rejects_bad_input(self):
        for data in (
            config([True, 2], 8, [0]), config([2, 0], 8, [0]),
            config([2, 2], 8, []), config([2, 2], 8, [-1]),
            config([2, 2], 8, [0], [["B", 1, 4], ["B", 3, 7]]),
            config([2, 2], 8, [0], [["X", 1, 4]]),
        ):
            with self.subTest(data=data), self.assertRaises(ValueError):
                simulate(data)

    def test_example_cli(self):
        root = Path(__file__).resolve().parents[1]
        for case, completed in {
            "baseline": 13, "faster-feed": 13, "faster-assemble": 18,
            "inspection-pause-zero": 11, "inspection-pause-two": 13,
        }.items():
            with self.subTest(case=case):
                run = subprocess.run([sys.executable, "line.py", f"examples/{case}.json"],
                                     cwd=root, check=True, capture_output=True, text=True)
                self.assertEqual(json.loads(run.stdout)["completed"], completed)


if __name__ == "__main__":
    unittest.main()
