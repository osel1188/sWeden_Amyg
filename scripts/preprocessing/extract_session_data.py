"""Extract voltage timeseries and metadata from TILA .log and CSV sessions.

Task contract:
    run_extract_session_data(input_items, output_dir, force=False) -> list[Path]

input_items:  list of session folder Paths or individual .log file Paths.
              Batch directories (containing session sub-folders) are also accepted.
output_dir:   root output directory — each session writes to output_dir/<session_name>/.
force:        when True, reprocess sessions whose outputs already exist.

Returns a flat list of all voltages.csv Paths produced (one per session).
"""

import csv
import json
import logging
import re
from pathlib import Path
from typing import List

import pandas as pd

from utils.should_process_task import should_process_task, clean_task_outputs

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

RAMP_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2},\d{3}) .+ "
    r"temporal_interference\.services\.manager - INFO - "
    r"Ramping channel '(\w+)' in system '(\w+)' to "
    r"([\d.]+(?:e[+-]?\d+)?)V at ([\d.]+) V/s\."
)

RAMP_FINISHED_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2},\d{3}) .+ "
    r"Ramp finished in [\d.]+s\. Final Voltages: \[(.+?)\]"
)

FREQ_RE = re.compile(
    r"Region (.+?)'s (\w+) side frequencies set to: "
    r"(\w+)=(\d+(?:\.\d+)?) Hz, (\w+)=(\d+(?:\.\d+)?) Hz\."
)

TARGET_V_RE = re.compile(
    r"Region (.+?)'s (\w+) side target voltages set to: "
    r"(\w+)=([\d.]+) V(?:, (\w+)=([\d.]+) V)?"
)

RAMP_DUR_RE = re.compile(
    r"Region (.+?)'s (\w+) side ramp durations set to: "
    r"(\w+)=(\d+)s(?:, (\w+)=(\d+)s)?"
)

PROTOCOL_CONDITION_RE = re.compile(r"Condition found: '(\w+)'\. Using as protocol\.")
PROTOCOL_INIT_RE = re.compile(r"Initializing protocol '(\w+)': (.+?)\.")

SAFETY_LIMIT_RE = re.compile(
    r"Safety limit .+: Max amplitude set to ([\d.]+) Vp\."
)

CHANNEL_MAP_RE = re.compile(
    r"Mapped logical channel '(\w+)' to driver '(\w+)' \(Phys Ch (\d+)\)"
)

SYSTEM_REGION_RE = re.compile(r"Found system: '(\w+)' targeting '(.+)'")

TIMESTAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2},\d{3})")

CSV_CHANNEL_MAP = {
    ("master", "1"): "A1", ("master", "2"): "A2",
    ("slave_1", "1"): "B1", ("slave_1", "2"): "B2",
}
CSV_VOLTAGE_RE = re.compile(r":?SOURce(\d):VOLTage\s+([\d.]+)")
CSV_APPLY_RE   = re.compile(r":?SOURce(\d):APPLy:SINusoid\s+([\d.]+),([\d.]+)")
CSV_SERIAL_RE  = re.compile(r"::(\w{10,})::0::INSTR")

CHANNELS = ["A1", "A2", "B1", "B2"]


# ---------------------------------------------------------------------------
# Parsing helpers (unchanged from 03_extract_session_data.py)
# ---------------------------------------------------------------------------


def _parse_voltage_list(s: str) -> list[tuple[str, float]]:
    pairs = []
    for item in s.split(", "):
        m = re.match(r"(\w+): ([\d.]+)V", item.strip())
        if m:
            pairs.append((m.group(1), round(float(m.group(2)), 1)))
    return pairs


def _extract_driver_serials(path: Path) -> dict[str, str]:
    driver_serials: dict[str, str] = {}
    init_re = re.compile(
        r"Initializing waveform generator: ID='(\w+)'.*"
        r"Resource='.*?::(\w+)::0::INSTR'"
    )
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = init_re.search(line)
            if m:
                driver_serials[m.group(1)] = m.group(2)
    return driver_serials


def _parse_num(s: str) -> int | float:
    f = float(s)
    if f == int(f):
        return int(f)
    return f


def _parse_gui_status(path: Path) -> dict:
    target_re = re.compile(r"Target voltages set: \[([\d. ]+)\]")
    condition_re = re.compile(r"Condition (\w+) selected")
    target_voltages = None
    condition = None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) < 3:
                continue
            msg = row[2]
            if target_voltages is None:
                m = target_re.search(msg)
                if m:
                    target_voltages = [float(v) for v in m.group(1).split()]
            if condition is None:
                m = condition_re.search(msg)
                if m:
                    condition = m.group(1)
    return {"target_voltages": target_voltages, "condition": condition}


def _parse_participant_txt(session_dir: Path) -> dict:
    txt_files = [f for f in session_dir.glob("*T*.txt")]
    if not txt_files:
        return {"participant_id": None, "sex": None, "randomization_number": None}
    result = {"participant_id": None, "sex": None, "randomization_number": None}
    with open(txt_files[0], "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("Participant ID:"):
                result["participant_id"] = line.split(":", 1)[1].strip()
            elif line.startswith("Selected Sex:"):
                result["sex"] = line.split(":", 1)[1].strip()
            elif line.startswith("Randomization Number:"):
                val = line.split(":", 1)[1].strip()
                result["randomization_number"] = int(val) if val.isdigit() else val
    return result


def parse_log_file(path: Path) -> dict:
    ramp_events: list[dict] = []
    metadata: dict = {
        "protocol": None,
        "protocol_description": None,
        "beat_frequency_hz": None,
        "generators": {},
        "safety_limit_vp": None,
        "ramp_rate_v_per_s": None,
        "frequencies": {},
        "default_target_voltages": {},
        "ramp_durations_s": {},
        "systems": {},
        "channel_map": {},
    }

    first_ts = None
    last_ts = None
    warning_count = 0
    error_count = 0
    total_lines = 0
    channel_driver: dict[str, str] = {}

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            total_lines += 1

            ts_m = TIMESTAMP_RE.match(line)
            if ts_m:
                ts_str = f"{ts_m.group(1)} {ts_m.group(2)}"
                if first_ts is None:
                    first_ts = ts_str
                last_ts = ts_str

            if " - WARNING - " in line:
                warning_count += 1
            if " - ERROR - " in line:
                error_count += 1

            m = RAMP_RE.match(line)
            if m:
                if metadata["ramp_rate_v_per_s"] is None:
                    metadata["ramp_rate_v_per_s"] = float(m.group(6))
                continue

            m = RAMP_FINISHED_RE.match(line)
            if m:
                date, time = m.group(1), m.group(2)
                for channel, voltage in _parse_voltage_list(m.group(3)):
                    ramp_events.append({
                        "date": date,
                        "time": time,
                        "channel": channel,
                        "voltage": voltage,
                    })
                continue

            m = PROTOCOL_CONDITION_RE.search(line)
            if m:
                metadata["protocol"] = m.group(1)
                continue

            m = PROTOCOL_INIT_RE.search(line)
            if m:
                metadata["protocol_description"] = m.group(2)
                bf_m = re.search(r"(\d+)\s*Hz\s*beat", m.group(2))
                if bf_m:
                    metadata["beat_frequency_hz"] = int(bf_m.group(1))
                continue

            m = SAFETY_LIMIT_RE.search(line)
            if m:
                metadata["safety_limit_vp"] = float(m.group(1))
                continue

            m = CHANNEL_MAP_RE.search(line)
            if m:
                channel, driver_id, phys_ch = m.group(1), m.group(2), int(m.group(3))
                channel_driver[channel] = driver_id
                metadata["channel_map"][channel] = {
                    "driver": driver_id,
                    "physical_channel": phys_ch,
                }
                continue

            m = SYSTEM_REGION_RE.search(line)
            if m:
                sys_id, region = m.group(1), m.group(2)
                metadata["systems"][sys_id] = region
                continue

            m = FREQ_RE.search(line)
            if m:
                side = m.group(2)
                ch1, freq1, ch2, freq2 = m.group(3), m.group(4), m.group(5), m.group(6)
                metadata["frequencies"][side] = {
                    ch1: _parse_num(freq1),
                    ch2: _parse_num(freq2),
                }
                continue

            m = TARGET_V_RE.search(line)
            if m:
                side = m.group(2)
                ch1, v1 = m.group(3), float(m.group(4))
                entry = {ch1: v1}
                if m.group(5) and m.group(6):
                    entry[m.group(5)] = float(m.group(6))
                if side not in metadata["default_target_voltages"]:
                    metadata["default_target_voltages"][side] = entry
                continue

            m = RAMP_DUR_RE.search(line)
            if m:
                side = m.group(2)
                ch1, dur1 = m.group(3), int(m.group(4))
                entry = {ch1: dur1}
                if m.group(5) and m.group(6):
                    entry[m.group(5)] = int(m.group(6))
                metadata["ramp_durations_s"][side] = entry
                continue

    ramp_events.sort(key=lambda e: (e["date"], e["time"]))

    driver_channels: dict[str, list[str]] = {}
    for ch, drv in sorted(channel_driver.items()):
        driver_channels.setdefault(drv, []).append(ch)

    driver_serials = _extract_driver_serials(path)

    for drv_id, channels in sorted(driver_channels.items()):
        sys_id = None
        region = None
        for s_id, s_region in metadata["systems"].items():
            for ev in ramp_events:
                if ev["channel"] in channels and ev.get("system") == s_id:
                    sys_id = s_id
                    region = s_region
                    break
            if sys_id:
                break

        metadata["generators"][drv_id] = {
            "serial": driver_serials.get(drv_id),
            "channels": channels,
            "system": sys_id,
            "region": region,
        }

    time_start = first_ts.replace(",", ".") if first_ts else None
    time_end = last_ts.replace(",", ".") if last_ts else None

    metadata["time_start"] = time_start
    metadata["time_end"] = time_end
    metadata["total_lines"] = total_lines
    metadata["warning_count"] = warning_count
    metadata["error_count"] = error_count
    metadata["ramp_event_count"] = len(ramp_events)

    return {"metadata": metadata, "ramp_events": ramp_events}


def parse_csv_session(session_dir: Path) -> dict:
    csv_files = sorted(session_dir.glob("*keysight_edu_comms.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No keysight_edu_comms.csv in {session_dir}")
    csv_path = csv_files[0]

    ramp_events: list[dict] = []
    frequencies: dict[str, float] = {}
    serials: dict[str, str] = {}

    with open(csv_path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) < 4:
                continue
            ts_raw, command, device_name, resource = row[0], row[1], row[2], row[3]

            if device_name not in serials:
                m = CSV_SERIAL_RE.search(resource)
                if m:
                    serials[device_name] = m.group(1)

            ts_m = re.match(r"(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})-(\d{2})-(\d{3})", ts_raw)
            if not ts_m:
                continue
            date = ts_m.group(1)
            time = f"{ts_m.group(2)}:{ts_m.group(3)}:{ts_m.group(4)}.{ts_m.group(5)}"

            m = CSV_VOLTAGE_RE.search(command)
            if m:
                src_num, voltage_str = m.group(1), m.group(2)
                channel = CSV_CHANNEL_MAP.get((device_name, src_num))
                if channel:
                    ramp_events.append({
                        "date": date,
                        "time": time,
                        "channel": channel,
                        "voltage": voltage_str,
                    })
                continue

            m = CSV_APPLY_RE.search(command)
            if m:
                src_num, freq_str = m.group(1), m.group(2)
                channel = CSV_CHANNEL_MAP.get((device_name, src_num))
                if channel and channel not in frequencies:
                    frequencies[channel] = _parse_num(freq_str)

    time_start = f"{ramp_events[0]['date']} {ramp_events[0]['time']}" if ramp_events else None
    time_end = f"{ramp_events[-1]['date']} {ramp_events[-1]['time']}" if ramp_events else None

    gui_files = sorted(session_dir.glob("*gui_status_messages.csv"))
    gui_data = _parse_gui_status(gui_files[0]) if gui_files else {"target_voltages": None, "condition": None}
    participant_data = _parse_participant_txt(session_dir)

    device_channel_map = {
        "master": {"channels": ["A1", "A2"]},
        "slave_1": {"channels": ["B1", "B2"]},
    }
    generators = {}
    for dev_name, info in device_channel_map.items():
        generators[dev_name] = {
            "serial": serials.get(dev_name),
            "channels": info["channels"],
            "system": None,
            "region": None,
        }

    metadata = {
        "protocol": gui_data["condition"],
        "protocol_description": None,
        "beat_frequency_hz": None,
        "generators": generators,
        "safety_limit_vp": None,
        "ramp_rate_v_per_s": None,
        "frequencies": frequencies,
        "default_target_voltages": (
            {"gui": gui_data["target_voltages"]} if gui_data["target_voltages"] else {}
        ),
        "ramp_durations_s": {},
        "systems": {},
        "channel_map": {},
        "participant": participant_data,
        "time_start": time_start,
        "time_end": time_end,
        "total_rows": len(ramp_events),
        "ramp_event_count": len(ramp_events),
    }

    return {"metadata": metadata, "ramp_events": ramp_events}


def build_voltage_df(ramp_events: list[dict], round_digits: int | None = None) -> pd.DataFrame:
    if not ramp_events:
        return pd.DataFrame(columns=["timestamp"] + CHANNELS)

    state = {ch: 0.0 for ch in CHANNELS}
    rows = []

    for ev in ramp_events:
        voltage = round(float(ev["voltage"]), round_digits) if round_digits is not None else ev["voltage"]
        state[ev["channel"]] = voltage
        ts = f"{ev['date']} {ev['time']}".replace(",", ".").split(".")[0]
        rows.append({"timestamp": ts, **{ch: state[ch] for ch in CHANNELS}})

    return pd.DataFrame(rows)


def _looks_like_session_folder(path: Path) -> bool:
    return bool(re.match(r"\d{4}-\d{2}-\d{2}_T?\d+", path.name))


def _append_session(session_dir: Path, results: list) -> None:
    log_files = sorted(session_dir.glob("*.log"))
    log_files = [f for f in log_files if "copy" not in f.name.lower()]
    if log_files:
        for lf in log_files:
            results.append((session_dir.name, "log", lf))
        return
    csv_files = sorted(session_dir.glob("*keysight_edu_comms.csv"))
    if csv_files:
        results.append((session_dir.name, "csv", session_dir))


def collect_sessions(input_path: Path) -> list[tuple[str, str, Path]]:
    results = []

    if input_path.is_file() and input_path.suffix == ".log":
        session_name = input_path.parent.name
        results.append((session_name, "log", input_path))
    elif input_path.is_dir():
        if _looks_like_session_folder(input_path):
            _append_session(input_path, results)
        else:
            for session_dir in sorted(input_path.iterdir()):
                if session_dir.is_dir():
                    _append_session(session_dir, results)

    return results


def _process_session(
    session_name: str,
    fmt: str,
    source_path: Path,
    output_dir: Path,
    force: bool,
) -> Path | None:
    """Process one session and return the output voltages.csv path, or None on skip."""
    out_dir = output_dir / session_name
    out_csv = out_dir / "voltages.csv"
    json_path = out_dir / "metadata.json"

    if not should_process_task(
        input_paths=[source_path],
        output_paths=[out_csv, json_path],
        force=force,
    ):
        return out_csv

    clean_task_outputs([out_csv, json_path])
    out_dir.mkdir(parents=True, exist_ok=True)

    if fmt == "log":
        result = parse_log_file(source_path)
    else:
        result = parse_csv_session(source_path)

    metadata = result["metadata"]
    ramp_events = result["ramp_events"]

    session_m = re.match(r"(\d{4}-\d{2}-\d{2})_(T?\d+)", session_name)
    if session_m:
        date = session_m.group(1)
        participant = session_m.group(2)
    else:
        date = None
        participant = None

    out_meta = {
        "session": session_name,
        "participant": participant,
        "date": date,
        "time_start": metadata["time_start"],
        "time_end": metadata["time_end"],
        "protocol": metadata["protocol"],
        "beat_frequency_hz": metadata["beat_frequency_hz"],
        "generators": metadata["generators"],
        "safety_limit_vp": metadata["safety_limit_vp"],
        "ramp_rate_v_per_s": metadata["ramp_rate_v_per_s"],
        "frequencies": metadata["frequencies"],
        "default_target_voltages": metadata["default_target_voltages"],
        "ramp_durations_s": metadata["ramp_durations_s"],
        "source_file": source_path.name,
        "source_format": fmt,
        "ramp_event_count": metadata["ramp_event_count"],
        "timeseries_interpolation": "zero_order_hold",
    }

    if fmt == "log":
        out_meta["total_lines"] = metadata["total_lines"]
        out_meta["warning_count"] = metadata["warning_count"]
        out_meta["error_count"] = metadata["error_count"]
    else:
        out_meta["total_rows"] = metadata["total_rows"]
        out_meta["warning_count"] = None
        out_meta["error_count"] = None
        out_meta["participant_info"] = metadata.get("participant")

    round_digits = 4 if fmt == "csv" else None
    df = build_voltage_df(ramp_events, round_digits=round_digits)

    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        f.write("# interpolation: zero_order_hold\n")
        df.to_csv(f, index=False)

    json_path.write_text(
        json.dumps(out_meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if fmt == "log":
        log.info(
            "%s: %d ramps, %d lines",
            session_name,
            metadata["ramp_event_count"],
            metadata["total_lines"],
        )
    else:
        log.info("%s: %d voltage rows", session_name, metadata["ramp_event_count"])

    return out_csv


# ---------------------------------------------------------------------------
# Task function
# ---------------------------------------------------------------------------


def run_extract_session_data(
    input_items: List[Path],
    output_dir: Path,
    force: bool = False,
) -> List[Path]:
    """Extract voltages.csv and metadata.json for each session in *input_items*.

    Args:
        input_items:  Session folder Paths or .log file Paths.  Batch directories
                      (containing session sub-folders) are also supported.
        output_dir:   Root output directory.  Each session writes to
                      output_dir/<session_name>/.
        force:        Reprocess sessions even if outputs already exist.

    Returns:
        List of voltages.csv Paths produced (one per session found).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect all sessions from the provided inputs
    sessions: list[tuple[str, str, Path]] = []
    for item in input_items:
        sessions.extend(collect_sessions(item))

    if not sessions:
        log.warning("No sessions found in input_items: %s", input_items)
        return []

    results: List[Path] = []
    for session_name, fmt, source_path in sessions:
        out_csv = _process_session(session_name, fmt, source_path, output_dir, force)
        if out_csv is not None:
            results.append(out_csv)

    return results


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

DEFAULT_INPUT = Path("backlogs_local_data/TILA_DATA_0_primary")
DEFAULT_OUTPUT = Path("backlogs_local_data/TILA_DATA_1_processed")


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Extract voltage timeseries and metadata from TILA .log and CSV sessions."
    )
    parser.add_argument(
        "input", nargs="?", type=Path, default=DEFAULT_INPUT,
        help=f"Input .log file, session folder, or batch directory (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=DEFAULT_OUTPUT,
        help=f"Output directory (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Reprocess sessions even if outputs already exist.",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Error: input not found: {args.input}")

    results = run_extract_session_data(
        input_items=[args.input],
        output_dir=args.output_dir,
        force=args.force,
    )
    print(f"Done. {len(results)} session(s) processed. Output in {args.output_dir}/")


if __name__ == "__main__":
    main()
