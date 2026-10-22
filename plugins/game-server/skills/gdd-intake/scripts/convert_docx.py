from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from gddlib.common import OperationResult, configure_utf8_streams
from gddlib.docx import convert_docx_file


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
        result = convert_docx_file(
            args.gdd_dir,
            args.source,
            args.output_root,
        )
        payload = _cli_payload(result, args.output_root)
    except (
        OSError,
        RuntimeError,
        UnicodeError,
        ValueError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"CONVERTED {result.source} -> {result.output}")
        details = payload["details"]
        print(f"Assets: {details['asset_directory']}")
        for removed in details["removed_asset_directories"]:
            print(f"Removed assets: {removed}")
    return 0


def _cli_payload(
    result: OperationResult,
    output_root: Path,
) -> dict[str, Any]:
    payload = asdict(result)
    details = payload["details"]
    output_base = output_root.resolve()
    details["asset_directory"] = _relative_output_path(
        details["asset_directory"],
        output_base,
    )
    details["removed_asset_directories"] = [
        _relative_output_path(path, output_base)
        for path in details["removed_asset_directories"]
    ]
    return payload


def _relative_output_path(path: str, output_root: Path) -> str:
    absolute = Path(path)
    try:
        return absolute.relative_to(output_root).as_posix()
    except ValueError as error:
        raise RuntimeError(
            f"conversion detail is outside output-root: {path}"
        ) from error


if __name__ == "__main__":
    configure_utf8_streams()
    raise SystemExit(main())
