"""Compatibility wrapper for the packaged readiness command."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mnemo.pipeline.ready import main


if __name__ == "__main__":
    raise SystemExit(main())
