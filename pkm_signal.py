#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SIGNAL_FILE = ROOT / "state" / "orb_signal.json"


def write_signal(thinking: bool, path: Path = SIGNAL_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"thinking": thinking, "updated_at": time.time()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Fast PKM orb signal switch")
    parser.add_argument("state", choices=["on", "off"])
    parser.add_argument("--file", type=Path, default=SIGNAL_FILE)
    args = parser.parse_args()
    write_signal(args.state == "on", args.file)
    print(f"thinking={args.state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
