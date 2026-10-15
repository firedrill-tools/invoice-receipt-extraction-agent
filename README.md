# Extract invoice and receipt fields from PDFs with Gemini

This command-line application sends one local invoice or receipt PDF to Gemini's document-understanding API, validates structured fields, and separately checks whether the extracted subtotal plus tax equals the printed total. It preserves a contradictory printed total instead of silently correcting it. The application uses `google-genai` 2.31.0 and has no payment, accounting, or file-upload side effects.

## Run one document

Install [uv](https://docs.astral.sh/uv/) and Python 3.11 or newer:

```sh
uv sync --dev
export GEMINI_API_KEY='your-key-from-a-secret-manager'
uv run extract-document --document data/documents/ordinary-invoice.pdf
```

The default model is `gemini-3.8-flash`, configurable through `EXTRACTOR_MODEL` or `--model`. The command makes one real Gemini API request and prints JSON only after extraction and arithmetic validation finish. The provider may charge for model usage. The document is sent inline; there is no remote file to clean up. The app rejects non-PDF input and PDFs over 10 MiB. Exit codes: `0` for a structured result, `2` for invalid input/configuration, `1` for an unexpected model/SDK failure.

The JSON has the source filename, model, extracted fields, `arithmetic_status` (`matches`, `mismatch`, or `unknown`), a computed total when arithmetic is possible, and SDK usage metadata when present. Null means a field was absent or illegible. A mismatch is an observation about the printed document and extraction; it is not automatically an agent failure.

## Sample situations

Three fictional, single-page PDFs live in `data/documents/`. Their cases are described in [scenarios/README.md](scenarios/README.md): a normal CAD invoice, a USD invoice whose printed total disagrees with its subtotal and tax, and a receipt whose identifier is unreadable. `scripts/make_fixtures.py` rebuilds the PDFs using reportlab. The sample PDFs are not customer data or recorded model results.

## Offline check and CI

```sh
uv sync --dev
uv run pytest -q
uv run extract-document --help
```

CI runs the same offline checks without a provider key. The tests cover PDF input validation, arithmetic, and the SDK call boundary with a fake client. They do not demonstrate real extraction quality. A live model proof will be recorded when an authorized key is available.

## Firedrill boundary and limits

The intended simulation seam is this one-document CLI with an explicit PDF path, JSON completion output, and no retained application state. A Firedrill integration is pending the new released interface and a verified persisted run. There is no claim of a Firedrill report or model result yet. Do not copy commands or configuration from the retired product.

The app handles PDFs only, not images, email attachments, OCR cleanup, or ledger posting. It does not decide whether a vendor should be paid. The repository is local and unlicensed pending the portfolio's publication decision.

Implementation references: [Gemini document understanding](https://ai.google.dev/gemini-api/docs/document-processing?lang=python) and [structured outputs](https://ai.google.dev/gemini-api/docs/structured-output?lang=python).

Explore related applications in the [Firedrill example catalog](https://github.com/firedrill-tools/firedrill-example-catalog). Product and setup references: [Firedrill](https://firedrill.run/) and the [official developer documentation](https://docs.firedrill.run/). Use documentation matching the qualified release; this repository records its current integration limits above.
