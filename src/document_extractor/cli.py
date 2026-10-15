"""One-document CLI entry point."""

import argparse
import os
import sys
from pathlib import Path

from pydantic import ValidationError

from .extract import extract_document


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract fields from one invoice or receipt PDF")
    parser.add_argument("--document", type=Path, required=True)
    parser.add_argument("--model", default=os.getenv("EXTRACTOR_MODEL", "gemini-3.8-flash"))
    args = parser.parse_args()
    try:
        if not os.getenv("GEMINI_API_KEY"):
            raise ValueError("GEMINI_API_KEY is required for a real model run")
        result = extract_document(args.document, model=args.model)
    except (OSError, ValueError, ValidationError) as exc:
        print(f"extract-document: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"extract-document: model request failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(result.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
