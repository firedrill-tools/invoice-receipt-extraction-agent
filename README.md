# Extract invoice and receipt fields from PDFs with Gemini

This CLI sends one local PDF to Gemini, validates structured fields, and separately checks whether the extracted subtotal plus tax equals the printed total. It preserves a contradictory printed total. It uses `google-genai` 2.31.0 and the foreground Interactions v1 API; it performs no payment or accounting operation.

## Run one document

Install [uv](https://docs.astral.sh/uv/) and Python 3.11 or newer:

```sh
uv sync --locked --dev
# Validate and list all ten synthetic inputs without a model or API key:
uv run --no-sync extract-document --list-cases
# Set GEMINI_API_KEY through your secret manager, then explicitly run one case:
uv run --no-sync extract-document --case ordinary-invoice
# Or supply one local PDF:
uv run --no-sync extract-document --document data/documents/ordinary-invoice.pdf
```

The default model is `gemini-3.8-flash`, configurable through `EXTRACTOR_MODEL` or `--model`. An explicit `GEMINI_API_KEY` is required; the CLI does not fall back to another Google key or Vertex account. One invocation starts one interaction with a 30-second HTTP timeout and a 4,096-output-token limit. It sends the document inline with `background=false` and `store=false`, without the Files API or remote cleanup. A real request can incur provider cost. Do not automatically run a batch or repeat campaign.

The pinned SDK normalizes `attempts=0` to one, then its Interactions adapter interprets that value as a retry count. A version- and configuration-guarded workaround sets the resource's exposed retry count to zero. Offline HTTP tests verify exactly one attempt on a 503. A dependency change must requalify that workaround. The application closes clients it creates on success and failure; an injected client's lifetime and retry policy belong to its caller.

Input preflight checks the `.pdf` suffix, `%PDF-` header and a 10 MiB maximum using a bounded read. This is not full PDF structural validation or malware inspection. For `--case`, the manifest SHA-256 is checked, and the exact checked bytes are sent even if the source file changes afterwards. `--manifest PATH` selects an explicit alternate dataset for `--case` or `--list-cases`; unknown cases, path escapes and digest drift fail before model access.

## Completion and evidence

Exit `0` produces one JSON object on stdout only after the interaction is `completed`, has no diagnostic errors, and its text passes field validation. Valid-looking JSON from an incomplete, cancelled, failed or nonfinal interaction is not a completed extraction. Missing or illegible values remain null. Dates must be valid ISO dates; money must be a plain decimal string, with all printed decimal places retained. Grouping such as `1,00` is rejected rather than silently interpreted.

The result includes the requested and returned model, interaction ID/status, source and prompt hashes, raw output text, validated fields, dataset identity when selected, exact `computed_total`, `arithmetic_status` (`matches`, `mismatch`, `unknown`), and review reasons. Arithmetic does not assume two decimal places, so JPY and three-decimal KWD values retain their precision. Missing fields, uncertainty, notes or printed arithmetic conflicts set `needs_review`; this is an observation, not an automatic agent score or payment decision.

Usage comes from Interactions' `usage` field. Absent usage stays null; partial counters are retained with `usage_complete=false`. Explicit zero counters remain distinct from missing counters. Provider totals can include thought tokens and need not equal input plus output. `cost_usd` stays null because tokens alone do not establish a billed price. Missing usage does not turn an otherwise valid extraction into a failure, and an HTTP error is not evidence of zero usage or cost.

Exit `2` is invalid input/configuration. Exit `1` is model, protocol or validation failure. Both produce JSON on stderr with no success stdout. Model failures retain the available observation, raw text, source/prompt hashes and case identity; they never produce accepted extracted fields. The CLI does not save journals. A caller redirecting output owns that evidence and should keep private documents and responses out of Git.

## Versioned synthetic documents

`data/manifest.json` identifies `northstar-extraction-documents` version `1.0.0`, with ten distinct PDFs across four profiles. All eleven pages were rendered and visually inspected. The receipt's smudged number has no underlying text-layer identifier. [Scenario briefs](scenarios/README.md) describe intended observations without providing model answers to the extraction request.

| Profile | Inputs | Coverage |
|---|---:|---|
| Starter | 2 | Clear invoice and narrow receipt layouts |
| Busy | 3 | Two-page line-item invoice, zero- and three-decimal currencies |
| Ambiguous | 3 | Conflicting total, bare dollar sign, customer reference without invoice number |
| Boundary | 2 | Illegible number, instructions printed inside document content |

`uv run --no-sync python scripts/make_fixtures.py` regenerates the documents and hashes with pinned ReportLab 4.4.9. Qualify a new dataset version when changing inputs; never quietly edit a PDF under an existing digest. The wheel bundles the manifest and all ten PDFs so case selection works outside the checkout.

## Offline check and CI

```sh
uv sync --locked --dev
uv run --no-sync pytest -q
uv run --no-sync extract-document --list-cases
uv build --wheel
uv run --no-sync python scripts/check_wheel.py
```

CI runs these checks without a provider key. Tests use the actual Gemini SDK with `httpx.MockTransport` for request serialization, response parsing, completion, usage, retry limits and cleanup. They also cover exact arithmetic, input drift, PDF page content, byte-for-byte fixture reproduction in a temporary directory, and the packaged CLI outside the checkout. These checks do not establish live extraction quality, prompt-injection resistance or provider availability. A live model proof remains pending an authorized key and budget.

## Firedrill boundary and limits

The intended simulation seam is this one-document CLI with explicit input identity, JSON completion evidence and no retained application state. A Firedrill integration awaits the new verified released interface and a persisted run. There is no claim of a Firedrill report or live Gemini result. Do not copy commands or configuration from the retired product.

The app handles PDFs, not images, email attachments, OCR cleanup or ledger posting. Public visibility and licensing remain pending the portfolio's publication decision.

Implementation references: [Interactions v1 API](https://ai.google.dev/api/interactions-api-v1), [Gemini document understanding](https://ai.google.dev/gemini-api/docs/document-processing?lang=python) and [structured outputs](https://ai.google.dev/gemini-api/docs/structured-output?lang=python).

Explore related applications in the [Firedrill example catalog](https://github.com/firedrill-tools/firedrill-example-catalog). Product and setup references: [Firedrill](https://firedrill.run/) and the [official developer documentation](https://docs.firedrill.run/). Use documentation matching the qualified release.
