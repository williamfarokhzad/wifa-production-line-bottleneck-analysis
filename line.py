"""A deterministic, offline serial production line with one-second time steps."""

import argparse
import json
from pathlib import Path


def parse(raw):
    def integer(value, low, high, label):
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{label} must be an integer from {low} to {high}")
        return value

    if not isinstance(raw, dict) or set(raw) - {"seconds", "stations", "buffers", "pauses"}:
        raise ValueError("expected an object with seconds, stations, buffers and optional pauses")
    horizon = integer(raw.get("seconds"), 1, 86400, "seconds")
    stations, buffers, pauses = (raw.get("stations"), raw.get("buffers"), raw.get("pauses", []))
    if not isinstance(stations, list) or not 2 <= len(stations) <= 8:
        raise ValueError("stations must be a list of 2 to 8 [name, cycle seconds] pairs")
    if any(not isinstance(row, list) or len(row) != 2
           or not isinstance(row[0], str) or not row[0].strip() for row in stations):
        raise ValueError("each station needs a nonempty name and a cycle")
    names = tuple(row[0] for row in stations)
    if len(set(names)) != len(names):
        raise ValueError("station names must be unique")
    cycles = tuple(integer(v, 1, 86400, f"{k} cycle") for k, v in stations)
    if not isinstance(buffers, list) or len(buffers) != len(names) - 1:
        raise ValueError("give one buffer size for each adjacent pair of stations")
    caps = tuple(integer(v, 0, 1000, "buffer capacity") for v in buffers)
    if not isinstance(pauses, list) or len(pauses) > 200:
        raise ValueError("pauses must be a list of up to 200 intervals")
    intervals = [[] for _ in names]
    for pause in pauses:
        if not isinstance(pause, list) or len(pause) != 3 or pause[0] not in names:
            raise ValueError("each pause must be [station name, start second, end second]")
        name, start, end = pause
        start = integer(start, 0, horizon - 1, "pause start")
        end = integer(end, start + 1, horizon, "pause end")
        intervals[names.index(name)].append((start, end))
    for periods in intervals:
        periods.sort()
        if any(a[1] > b[0] for a, b in zip(periods, periods[1:])):
            raise ValueError("pause intervals for one station cannot overlap")
    return horizon, names, cycles, caps, intervals


def simulate(raw):
    horizon, names, cycles, caps, intervals = parse(raw)
    n = len(names)
    # None is empty; 0 is finished and waiting for space; >0 is remaining work.
    remaining = [None] * n
    queues = [0] * (n - 1)
    peaks = queues.copy()
    pause_index = [0] * n
    states = [{key: 0 for key in ("working", "blocked", "starved", "offline")} for _ in names]
    finished = []
    admitted = 0

    for t in range(horizon + 1):
        online = []
        for i, periods in enumerate(intervals):
            j = pause_index[i]
            if j < len(periods) and t >= periods[j][1]:
                j += 1
                pause_index[i] = j
            online.append(j == len(periods) or t < periods[j][0])

        # Settle the boundary downstream first. Existing queued parts enter first.
        # A free online receiver can take a direct handoff even with zero slots.
        if remaining[-1] == 0:
            finished.append(t)
            remaining[-1] = None
        if t == horizon:
            break
        for i in range(n - 2, -1, -1):
            receiver = i + 1
            available = remaining[receiver] is None and online[receiver]
            if queues[i] and available:
                queues[i] -= 1
                remaining[receiver] = cycles[receiver]
                available = False
            if remaining[i] == 0:
                if available:
                    remaining[receiver] = cycles[receiver]
                elif queues[i] < caps[i]:
                    queues[i] += 1
                    peaks[i] = max(peaks[i], queues[i])
                else:
                    continue
                remaining[i] = None

        if remaining[0] is None and online[0]:
            remaining[0] = cycles[0]
            admitted += 1
        for i, todo in enumerate(remaining):
            if not online[i]:
                state = "offline"
            elif todo is None:
                state = "starved"
            elif todo == 0:
                state = "blocked"
            else:
                state = "working"
                remaining[i] -= 1
            states[i][state] += 1

    return {
        "seconds": horizon,
        "admitted": admitted,
        "completed": len(finished),
        "completion_times_s": finished,
        "observed_parts_per_hour": round(3600 * len(finished) / horizon, 3),
        "unfinished": sum(v is not None for v in remaining) + sum(queues),
        "peak_waiting_parts": peaks,
        "station_seconds": dict(zip(names, states)),
        "isolated_completion_upper_bound": min(
            (horizon - s["offline"]) // cycle for s, cycle in zip(states, cycles)
        ),
    }


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("scenario", type=Path)
    args = cli.parse_args()
    try:
        report = simulate(read_json(args.scenario))
    except (OSError, ValueError) as exc:
        cli.error(str(exc))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
