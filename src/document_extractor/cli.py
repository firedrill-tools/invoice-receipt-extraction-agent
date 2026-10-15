"""One-document CLI with distinct successful extraction and failure evidence."""

import argparse
from hashlib import sha256
import json
import os
import sys
from pathlib import Path

from .datasets import DEFAULT_MANIFEST, describe_cases, select_case
from .extract import PROMPT, ExtractionRunError, extract_document, load_pdf


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract fields from one invoice or receipt PDF")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--document", type=Path)
    source.add_argument("--case", help="Select one versioned PDF and make one real model request")
    source.add_argument("--list-cases", action="store_true", help="Validate/list PDF inputs without provider access")
    parser.add_argument("--manifest", type=Path, help="Explicit manifest for --case or --list-cases")
    parser.add_argument("--model", default=os.getenv("EXTRACTOR_MODEL", "gemini-3.8-flash"))
    args = parser.parse_args(argv)
    if args.manifest is not None and not (args.case or args.list_cases):
        parser.error("--manifest requires --case or --list-cases")
    dataset = None
    try:
        manifest = args.manifest or DEFAULT_MANIFEST
        if args.list_cases:
            print(json.dumps(describe_cases(manifest)))
            return 0
        if args.case:
            path, data, dataset = select_case(args.case, manifest)
        else:
            path = args.document
            data = load_pdf(path)
        if not os.getenv("GEMINI_API_KEY"):
            raise ValueError("GEMINI_API_KEY is required for a real model run")
        result = extract_document(path, model=args.model, pdf_data=data)
        result.dataset = dataset
    except ExtractionRunError as exc:
        print(json.dumps({"error": {"code": "model_failed", "message": str(exc), "type": exc.provider_error_type,
                                   "http_status": exc.http_status},
            "observation": exc.observation.model_dump(mode="json"), "raw_output": exc.raw_output,
            "source_sha256": exc.source_sha256, "prompt_sha256": sha256(PROMPT.encode()).hexdigest(),
            "dataset": dataset.model_dump() if dataset is not None else None}), file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": {"code": "invalid_input_or_configuration", "message": str(exc)}}), file=sys.stderr)
        return 2
    except Exception as exc:
        print(json.dumps({"error": {"code": "model_failed", "type": type(exc).__name__}}), file=sys.stderr)
        return 1
    print(result.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
