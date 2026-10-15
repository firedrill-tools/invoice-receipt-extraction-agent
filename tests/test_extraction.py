"""Actual google-genai serialization/parsing over a local HTTP transport; no API access."""

import base64
from hashlib import sha256
import json
from pathlib import Path

from google import genai
import httpx
import pytest
from pydantic import ValidationError

from document_extractor import cli
from document_extractor import extract as adapter
from document_extractor.datasets import select_case
from document_extractor.extract import ExtractionRunError, PROMPT, extract_document, load_pdf
from document_extractor.models import ArithmeticStatus, ExtractedFields, check_arithmetic

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = ROOT / "data/documents"
MODEL = "gemini-3.8-flash"
FIELDS = {
    "document_type": "invoice", "vendor_name": "Harbor Supplies", "document_number": "INV-2041",
    "issue_date": "2026-10-01", "currency": "CAD", "subtotal": "180.00", "tax": "23.40",
    "total": "203.40", "uncertain_fields": [], "notes": None,
}
USAGE = {"total_input_tokens": 25, "total_output_tokens": 12, "total_thought_tokens": 8, "total_tokens": 45}


def response(*, fields=None, text=None, status="completed", usage=USAGE, errors=None):
    body = {"id": "synthetic-interaction", "status": status, "model": MODEL,
            "steps": [{"type": "model_output", "content": [{"type": "text", "text":
                json.dumps(FIELDS if fields is None else fields) if text is None else text}]}]}
    if usage is not None:
        body["usage"] = usage
    if errors is not None:
        body["errors"] = errors
    return body


@pytest.fixture(autouse=True)
def no_ambient_credentials(monkeypatch):
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI", "EXTRACTOR_MODEL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def sdk():
    opened = []

    def make(body=None, status=200, handler=None, configure=True):
        requests = []

        def local(request):
            requests.append(request)
            return handler(request) if handler else httpx.Response(status, json=response() if body is None else body)

        transport = httpx.Client(transport=httpx.MockTransport(local))
        client = genai.Client(api_key="synthetic-not-a-secret", vertexai=False,
            http_options={"api_version": "v1", "httpx_client": transport, "timeout": 30000,
                          "retry_options": {"attempts": 1}})
        if configure:
            adapter.disable_interaction_retries(client)
        opened.append((client, transport))
        return client, requests, transport

    yield make
    for client, transport in opened:
        client.close()
        transport.close()


def run(client):
    return extract_document(DOCUMENTS / "ordinary-invoice.pdf", model=MODEL, client=client)


def test_real_sdk_sends_only_pdf_snapshot_prompt_schema_and_bounded_foreground_options(sdk):
    client, requests, transport = sdk()
    result = run(client)
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://generativelanguage.googleapis.com/v1/interactions"
    body = json.loads(request.content)
    assert body["model"] == MODEL
    assert body["background"] is False and body["store"] is False
    assert body["generation_config"] == {"max_output_tokens": 4096}
    assert len(body["input"]) == 1
    assert body["input"][0]["type"] == "user_input"
    parts = body["input"][0]["content"]
    assert len(parts) == 2
    assert parts[0]["type"] == "document"
    assert parts[0]["mime_type"] == "application/pdf"
    sent = base64.b64decode(parts[0]["data"], validate=True)
    assert sent == (DOCUMENTS / "ordinary-invoice.pdf").read_bytes()
    assert parts[1] == {"type": "text", "text": PROMPT}
    assert body["response_format"]["schema"] == ExtractedFields.model_json_schema()
    assert body["response_format"]["mime_type"] == "application/json"
    assert result.fields.model_dump(mode="json") == FIELDS
    assert result.source_sha256 == sha256(sent).hexdigest()
    assert result.prompt_sha256 == sha256(PROMPT.encode()).hexdigest()
    assert result.computed_total == "203.40" and result.needs_review is False
    assert result.usage == USAGE  # Includes thought tokens: not input + output.
    assert result.observation.usage_complete is True
    assert result.observation.interaction_id == "synthetic-interaction"
    assert result.observation.response_model == MODEL
    assert result.observation.cost_usd is None
    assert not transport.is_closed  # Injected client remains caller-owned.


@pytest.mark.parametrize("status", ["in_progress", "requires_action", "failed", "cancelled", "incomplete"])
def test_noncompleted_valid_looking_json_is_failure_with_evidence(sdk, status):
    client, requests, _ = sdk(response(status=status))
    with pytest.raises(ExtractionRunError) as caught:
        run(client)
    assert len(requests) == 1
    assert caught.value.observation.status == status
    assert caught.value.observation.reported_usage == USAGE
    assert json.loads(caught.value.raw_output) == FIELDS


@pytest.mark.parametrize("usage,complete", [
    (None, False), ({}, False), ({"total_input_tokens": 25}, False),
    ({"total_input_tokens": 0, "total_output_tokens": 0, "total_tokens": 0}, True),
    ({"total_input_tokens": -1, "total_output_tokens": 12, "total_tokens": 11}, False),
])
def test_missing_partial_zero_and_invalid_usage_remain_distinct(sdk, usage, complete):
    client, _, _ = sdk(response(usage=usage))
    result = run(client)
    assert result.usage == usage
    assert result.observation.usage_complete is complete
    assert result.observation.cost_usd is None


@pytest.mark.parametrize("text", ["", " ", "not json", '{"document_type":"invoice"}',
                                  json.dumps({**FIELDS, "total": "1,00"})])
def test_bad_model_output_is_model_failure_not_input_configuration(sdk, text):
    client, _, _ = sdk(response(text=text))
    with pytest.raises(ExtractionRunError) as caught:
        run(client)
    assert caught.value.observation.status == "completed"
    assert caught.value.observation.reported_usage == USAGE
    assert caught.value.raw_output == text


def test_diagnostic_errors_fail_even_when_status_and_json_look_complete(sdk):
    client, _, _ = sdk(response(errors=[{"code": "INTERNAL", "message": "synthetic fault"}]))
    with pytest.raises(ExtractionRunError) as caught:
        run(client)
    assert caught.value.observation.diagnostic_error_count == 1


@pytest.mark.parametrize("failure", [False, True])
def test_owned_client_closes_after_success_or_failure_and_pins_transport_options(sdk, monkeypatch, failure):
    client, requests, _ = sdk(response(status="failed" if failure else "completed"), configure=False)
    closed = []
    original_close = client.close

    def close():
        closed.append(True)
        original_close()

    monkeypatch.setattr(client, "close", close)

    def construct(**kwargs):
        assert kwargs == {"api_key": "synthetic-not-a-secret", "vertexai": False,
            "http_options": {"api_version": "v1", "timeout": 30000, "retry_options": {"attempts": 1}}}
        return client

    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-not-a-secret")
    monkeypatch.setattr(adapter.genai, "Client", construct)
    if failure:
        with pytest.raises(ExtractionRunError):
            extract_document(DOCUMENTS / "ordinary-invoice.pdf", model=MODEL)
    else:
        extract_document(DOCUMENTS / "ordinary-invoice.pdf", model=MODEL)
    assert closed == [True] and len(requests) == 1


def test_http_503_has_no_hidden_retry_and_keeps_unknown_usage(sdk):
    client, requests, _ = sdk({"error": {"code": 503, "message": "synthetic unavailability", "status": "UNAVAILABLE"}}, status=503)
    with pytest.raises(ExtractionRunError) as caught:
        run(client)
    assert len(requests) == 1
    assert caught.value.http_status == 503
    assert caught.value.observation.reported_usage is None
    assert caught.value.observation.usage_complete is False
    assert caught.value.raw_output is None


@pytest.mark.parametrize("subtotal,tax,total,computed,status", [
    ("125.00", "10.00", "130.00", "135.00", "mismatch"),
    ("12.345", "0.617", "12.962", "12.962", "matches"),
    ("1000", "100", "1100", "1100", "matches"),
    ("999999999999999999999999999999.99", "0.01", "1000000000000000000000000000000.00", "1000000000000000000000000000000.00", "matches"),
    (None, "0.00", "9.50", None, "unknown"),
    ("-5.00", "0.50", "-4.50", "-4.50", "matches"),
])
def test_arithmetic_preserves_printed_values_and_full_precision(subtotal, tax, total, computed, status):
    fields = ExtractedFields(**{**FIELDS, "subtotal": subtotal, "tax": tax, "total": total})
    assert check_arithmetic(fields) == (status, computed)
    assert fields.total == total


@pytest.mark.parametrize("field,value", [
    ("subtotal", "1,00"), ("tax", "NaN"), ("total", "1e3"), ("total", " 1.00"),
    ("total", "1" * 129), ("issue_date", "2026-02-30"), ("issue_date", "20261001"),
    ("currency", "$"), ("currency", "usd"), ("vendor_name", "  "),
    ("document_number", ""), ("uncertain_fields", ["account_number"]), ("unexpected", True),
])
def test_invalid_structured_fields_are_rejected(field, value):
    with pytest.raises(ValidationError):
        ExtractedFields(**{**FIELDS, field: value})


def test_missing_id_and_printed_conflict_request_review_without_rewriting(sdk):
    client, _, _ = sdk(response(fields={**FIELDS, "document_number": None, "total": "200.00", "uncertain_fields": ["document_number"]}))
    result = run(client)
    assert result.needs_review
    assert result.review_reasons == ["missing:document_number", "uncertain_fields", "printed_arithmetic_mismatch"]
    assert result.fields.document_number is None and result.fields.total == "200.00"
    assert result.arithmetic_status is ArithmeticStatus.MISMATCH


def test_selected_bytes_remain_bound_when_source_changes_after_selection(sdk, tmp_path):
    source, snapshot, selected = select_case("ordinary-invoice")
    changed = tmp_path / source.name
    changed.write_bytes(b"%PDF-changed-after-selection")
    client, requests, _ = sdk()
    result = extract_document(changed, model=MODEL, client=client, pdf_data=snapshot)
    assert result.source_sha256 == selected.source_sha256
    assert base64.b64decode(json.loads(requests[0].content)["input"][0]["content"][0]["data"]) == snapshot


def test_cli_case_carries_identity_and_never_sends_manifest(sdk, monkeypatch, capsys):
    client, requests, _ = sdk(configure=False)
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-not-a-secret")
    monkeypatch.setattr(adapter.genai, "Client", lambda **kwargs: client)
    assert cli.main(["--case", "ordinary-invoice"]) == 0
    output = capsys.readouterr()
    assert output.err == ""
    body = json.loads(output.out)
    assert body["dataset"]["case_id"] == "ordinary-invoice"
    assert body["dataset"]["version"] == "1.0.0"
    assert body["dataset"]["source_sha256"] == body["source_sha256"]
    assert b"northstar-extraction-documents" not in requests[0].content


def test_cli_failed_output_is_only_stderr_and_retains_observation(sdk, monkeypatch, capsys):
    client, _, _ = sdk(response(text="not json"), configure=False)
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-not-a-secret")
    monkeypatch.setattr(adapter.genai, "Client", lambda **kwargs: client)
    assert cli.main(["--case", "ordinary-invoice"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    body = json.loads(output.err)
    assert body["error"]["code"] == "model_failed"
    assert body["raw_output"] == "not json"
    assert body["observation"]["reported_usage"] == USAGE
    assert body["dataset"]["source_sha256"] == body["source_sha256"]


def test_missing_explicit_key_is_configuration_error_even_with_google_key(monkeypatch, capsys):
    monkeypatch.setenv("GOOGLE_API_KEY", "synthetic-other-account")
    monkeypatch.setattr(adapter.genai, "Client", lambda **kwargs: pytest.fail("must not create a provider client"))
    assert cli.main(["--case", "ordinary-invoice"]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err)["error"]["code"] == "invalid_input_or_configuration"


@pytest.mark.parametrize("model", ["other-model", "gemini-", "gemini-x y"])
def test_invalid_model_never_constructs_client(monkeypatch, model):
    monkeypatch.setattr(adapter.genai, "Client", lambda **kwargs: pytest.fail("must not create a provider client"))
    with pytest.raises(ValueError, match="Gemini model"):
        extract_document(DOCUMENTS / "ordinary-invoice.pdf", model=model)


@pytest.mark.parametrize("filename,content", [("fake.pdf", b"not a PDF"), ("fake.txt", b"%PDF-1.4")])
def test_invalid_pdf_preflight(filename, content, tmp_path):
    path = tmp_path / filename
    path.write_bytes(content)
    with pytest.raises(ValueError):
        load_pdf(path)


def test_oversized_input_rejected_before_client(tmp_path, monkeypatch):
    path = tmp_path / "large.pdf"
    path.write_bytes(b"%PDF-" + b"x" * adapter.MAX_DOCUMENT_BYTES)
    monkeypatch.setattr(adapter.genai, "Client", lambda **kwargs: pytest.fail("must not create a provider client"))
    with pytest.raises(ValueError, match="10 MiB"):
        extract_document(path, model=MODEL)


def test_retry_workaround_refuses_unqualified_sdk_change_and_closes_owned_client(sdk, monkeypatch):
    client, requests, _ = sdk(configure=False)
    closed = []
    original_close = client.close
    def close():
        closed.append(True)
        original_close()
    monkeypatch.setattr(client, "close", close)
    monkeypatch.setattr(adapter, "version", lambda package: "unqualified-version")
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-not-a-secret")
    monkeypatch.setattr(adapter.genai, "Client", lambda **kwargs: client)
    with pytest.raises(ExtractionRunError, match="RuntimeError"):
        extract_document(DOCUMENTS / "ordinary-invoice.pdf", model=MODEL)
    assert closed == [True] and requests == []
