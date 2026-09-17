"""Rebuild the whole library. Offline unless --fetch is given.

    python scripts/build.py           # csv -> sqlite + kicad_dbl -> footprints (uses raw/ cache)
    python scripts/build.py --fetch   # download fresh part data from JLCPCB first
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGES = ["fetch_parts.py", "build_csv.py", "build_db.py", "gen_footprints.py"]


def main():
    stages = STAGES if "--fetch" in sys.argv else STAGES[1:]
    for stage in stages:
        print(f"\n=== {stage} ===", flush=True)
        subprocess.run([sys.executable, str(HERE / stage)], check=True)


if __name__ == "__main__":
    main()
