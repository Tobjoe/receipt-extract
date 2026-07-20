"""Command-line interface: ``receipt-extract ingest|eval``.

The ingest command needs a real Anthropic client and API key. Eval runs fully
offline against a deterministic stub extractor (see ``eval`` package).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

DEFAULT_MODEL = "claude-sonnet-4-5"
DEFAULT_DB = "receipts.db"


def _build_client():
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set. Ingest needs a live key; "
            "run `receipt-extract eval` for the offline demo."
        )
    return anthropic.Anthropic(api_key=api_key)


def _cmd_ingest(args: argparse.Namespace) -> int:
    from receipt_extract.extraction import ReceiptExtractor
    from receipt_extract.pipeline import ingest
    from receipt_extract.storage import ReceiptStore

    client = _build_client()
    extractor = ReceiptExtractor(client=client, model=args.model)
    store = ReceiptStore(args.db)
    try:
        result = ingest(Path(args.path), extractor, store)
    finally:
        store.close()
    status = "cached" if result.was_cached else "stored"
    print(f"[{status}] receipt #{result.receipt_id}: "
          f"{result.receipt.vendor} {result.receipt.total} {result.receipt.currency}")
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    from receipt_extract.eval import run_offline_eval

    report = run_offline_eval(Path(args.golden), Path(args.out))
    print(report.render_table())
    print(f"\nReport written to {args.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="receipt-extract")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="extract one receipt into the database")
    ingest.add_argument("path", help="path to an image or PDF")
    ingest.add_argument("--model", default=DEFAULT_MODEL)
    ingest.add_argument("--db", default=DEFAULT_DB)
    ingest.set_defaults(func=_cmd_ingest)

    ev = sub.add_parser("eval", help="run offline evaluation against golden data")
    ev.add_argument("--golden", default="data/golden")
    ev.add_argument("--out", default="eval_report.json")
    ev.set_defaults(func=_cmd_eval)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
