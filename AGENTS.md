# Agent guide

The application entry point is `extract-document` in `src/document_extractor/cli.py`. `src/document_extractor/extract.py` owns the Gemini SDK boundary. It sends the PDF inline and validates the returned JSON; `models.py` performs a separate deterministic arithmetic check without rewriting extracted values.

- Configuration: set `GEMINI_API_KEY` through a secret manager. The default model is `gemini-3.8-flash`, configurable with `EXTRACTOR_MODEL` or `--model`.
- Input: one local PDF of at most 10 MiB. No network document URL or production document store is supported.
- State/reset: stateless. No uploaded file, background job, or external business operation remains after the request. Each invocation is independent.
- Samples: `data/documents/` contains three fictional PDFs; `scripts/make_fixtures.py` reproduces them using reportlab. Scenario intent is in `scenarios/README.md`.
- Completion: JSON stdout after the Gemini interaction returns and field validation/arithmetic finish. Exit `2` is input/configuration failure; exit `1` is an unexpected model/SDK failure.
- Safe offline check: `uv sync --dev && uv run pytest -q && uv run extract-document --help`. No model call occurs.
- Small live proof: with an authorized key, `uv run extract-document --document data/documents/ordinary-invoice.pdf`. This sends the fictional document to Gemini and may incur provider cost. Do not run all documents or repetitions automatically.
- Evidence: the output contains model identifier, extracted fields, arithmetic status and SDK usage metadata if supplied. There is no recorded live model result yet.
- Authorization: do not add customer PDFs, credentials, private output journals, or invented evaluation results. A new Firedrill connection must use its verified released interface, not the old drills.
