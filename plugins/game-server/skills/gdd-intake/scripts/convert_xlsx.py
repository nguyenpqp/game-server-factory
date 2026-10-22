from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Sequence

from gddlib.common import configure_utf8_streams
from gddlib.xlsx import convert_xlsx_file


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gdd-dir", required=True, type=Path)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    try:
        result = convert_xlsx_file(
            args.gdd_dir,
            args.source,
            args.output_root,
        )
    except (OSError, RuntimeError, UnicodeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(asdict(result), ensure_ascii=False))
    else:
        print(f"CONVERTED {result.source} -> {result.output}")
    return 0


if __name__ == "__main__":
    configure_utf8_streams()
    raise SystemExit(main())
