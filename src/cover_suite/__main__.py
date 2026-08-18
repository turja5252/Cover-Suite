# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from __future__ import annotations

import argparse
import os

from cover_suite.gui import main


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="cover_suite")
    parser.add_argument(
        "--output-dir",
        default=os.environ.get("ELITE_COVER_OUTPUT", ""),
        help="Prefill the output folder (Databook Engine sets this when launching Cover Suite).",
    )
    parser.add_argument(
        "--job-number",
        default=os.environ.get("ELITE_COVER_JOB", ""),
        help="Prefill the job number (Databook Engine sets this from Page 1).",
    )
    parser.add_argument("--client", default=os.environ.get("ELITE_COVER_CLIENT", ""))
    parser.add_argument("--description", default=os.environ.get("ELITE_COVER_DESCRIPTION", ""))
    parser.add_argument("--location", default=os.environ.get("ELITE_COVER_LOCATION", ""))
    parser.add_argument("--tag", default=os.environ.get("ELITE_COVER_TAG", ""))
    parser.add_argument("--revision", default=os.environ.get("ELITE_COVER_REVISION", ""))
    parser.add_argument("--tab-title", default=os.environ.get("ELITE_COVER_TAB", ""))
    parser.add_argument("--font", default=os.environ.get("ELITE_COVER_FONT", ""))
    args = parser.parse_args(argv)
    fields = {
        "client": str(args.client or "").strip(),
        "description": str(args.description or "").strip(),
        "location": str(args.location or "").strip(),
        "tag": str(args.tag or "").strip(),
        "revision": str(args.revision or "").strip(),
        "tab_title": str(args.tab_title or "").strip(),
        "font": str(args.font or "").strip(),
    }
    main(
        output_dir=str(args.output_dir or "").strip() or None,
        job_number=str(args.job_number or "").strip() or None,
        fields=fields,
    )


if __name__ == "__main__":
    cli()
