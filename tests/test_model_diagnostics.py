"""Credential redaction checks with synthetic markers, never model execution."""

import hashlib
import json
from pathlib import Path

import pytest

from oak.model import (
    ModelInterruptedError,
    ModelOutputError,
    estimated_usage,
    redact_diagnostic,
    runtime_config,
    validate_cli_completion,
)


@pytest.mark.parametrize(
    "diagnostic",
    [
        "refresh_token=TEST_REFRESH_SECRET&client_secret=TEST_CLIENT_SECRET&grant_type=refresh_token",
        "{ refresh_token: 'TEST_REFRESH_SECRET', client_secret: 'TEST_CLIENT_SECRET', code: 'ENOTFOUND' }",
        '{"access_token":"TEST_ACCESS_SECRET","client_id":"TEST_CLIENT_ID","status":401}',
        "Authorization: Bearer TEST_BEARER_SECRET\ncode: ENOTFOUND",
        "Authorization: 'Bearer TEST_BEARER_SECRET'\ncode: ENOTFOUND",
        '{"error":"request {\\"refresh_token\\":\\"TEST_REFRESH_SECRET\\"}"}',
        'private_key: "-----BEGIN PRIVATE KEY-----\\nTEST_PRIVATE_SECRET\\n-----END PRIVATE KEY-----"',
        "_refreshToken: 'TEST_REFRESH_SECRET', _clientSecret: 'TEST_CLIENT_SECRET'",
        "URLSearchParams { 'refresh_token' => 'TEST_REFRESH_SECRET', 'client_secret' => 'TEST_CLIENT_SECRET' }",
    ],
)
def test_credentials_are_removed_without_model_calls(diagnostic: str) -> None:
    result = redact_diagnostic(diagnostic)
    assert "TEST_" not in result
    assert "[REDACTED" in result


def test_transport_status_and_usage_fields_remain_visible() -> None:
    text = (
        '{"error":"getaddrinfo ENOTFOUND oauth2.googleapis.com",'
        '"access_token":"TEST_ACCESS_SECRET","token_uri":"https://oauth2.googleapis.com/token",'
        '"stats":{"tokens":17},"returncode":1}'
    )
    clean = json.loads(redact_diagnostic(text))
    assert clean["error"] == "getaddrinfo ENOTFOUND oauth2.googleapis.com"
    assert clean["token_uri"] == "https://oauth2.googleapis.com/token"
    assert clean["stats"] == {"tokens": 17}
    assert clean["returncode"] == 1
    assert clean["access_token"] == "[REDACTED]"


def test_timeout_bytes_and_absent_output_are_supported() -> None:
    assert "TEST_SECRET" not in redact_diagnostic(b"password=TEST_SECRET\xff")
    assert redact_diagnostic(None) == ""


def test_actual_interrupted_cli_response_is_not_a_formatting_repair() -> None:
    """Replay actual metadata, without invoking a provider or fabricating output."""
    directory = Path(__file__).parent / "fixtures/model"
    raw = (directory / "interrupted-cli.json").read_bytes()
    provenance = json.loads((directory / "interrupted-cli.provenance.json").read_text())
    assert hashlib.sha256(raw).hexdigest() == provenance["derivative_sha256"]
    receipt = json.loads(raw)
    assert receipt["returncode"] == 0
    assert receipt["outer"]["stats"]["tools"]["totalCalls"] == 0
    with pytest.raises(json.JSONDecodeError):
        json.loads(receipt["outer"]["response"])
    with pytest.raises(ModelInterruptedError) as caught:
        validate_cli_completion(receipt["outer"], receipt["returncode"])
    assert not isinstance(caught.value, ModelOutputError)
    assert estimated_usage(receipt["outer"]["stats"], runtime_config()) is None
