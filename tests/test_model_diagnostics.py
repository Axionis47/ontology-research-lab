"""Credential redaction checks with synthetic markers, never model execution."""

import json

import pytest

from oak.model import redact_diagnostic


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
