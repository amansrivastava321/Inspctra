"""
test_prompt_safety.py - Tests for prompt_safety.py

Covers: API key redaction, DB URL redaction, private code cloud blocking,
bearer token redaction, JWT redaction, private key redaction.
"""
from __future__ import annotations

import pytest
from qa_ai.ai.prompt_safety import make_safe, redact_for_logging


class TestAPIKeyRedaction:
    def test_openai_key_redacted(self):
        r = make_safe("use key sk-abcdefghijklmnopqrstuvwxyz123456")
        assert "sk-abc" not in r.safe_prompt
        assert "[REDACTED" in r.safe_prompt

    def test_openrouter_key_redacted(self):
        r = make_safe("key is sk-or-v1-abcdefghijklmnopqrstuvwxyz0123456789")
        assert "sk-or-v1" not in r.safe_prompt
        assert "[REDACTED" in r.safe_prompt

    def test_bearer_token_redacted(self):
        r = make_safe("Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.abc")
        assert "eyJhbGciOiJSUzI1NiJ9" not in r.safe_prompt

    def test_jwt_token_redacted(self):
        jwt = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyMTIzIn0.signature_here_long_enough"
        r = make_safe(f"token: {jwt}")
        assert "eyJhbGciOiJSUzI1NiJ9" not in r.safe_prompt

    def test_plain_text_unchanged(self):
        r = make_safe("Hello, world!")
        assert r.safe_prompt == "Hello, world!"
        assert not r.redactions_applied

    def test_redactions_applied_list_populated(self):
        r = make_safe("key: sk-abcdefghijklmnopqrstuvwxyz123456")
        assert len(r.redactions_applied) > 0


class TestDatabaseURLRedaction:
    def test_postgres_url_with_creds_redacted(self):
        r = make_safe("db: postgres://admin:s3cr3t@localhost:5432/mydb")
        assert "s3cr3t" not in r.safe_prompt
        assert "REDACTED" in r.safe_prompt

    def test_mysql_url_with_creds_redacted(self):
        r = make_safe("mysql://root:password123@db.internal:3306/prod")
        assert "password123" not in r.safe_prompt

    def test_mongodb_url_redacted(self):
        r = make_safe("mongodb://user:pass@cluster0.mongodb.net/mydb")
        assert "pass@" not in r.safe_prompt


class TestPrivateKeyRedaction:
    def test_private_key_block_redacted(self):
        key_text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAK...\n-----END RSA PRIVATE KEY-----"
        r = make_safe(key_text)
        assert "MIIEowIBAAK" not in r.safe_prompt

    def test_password_pattern_redacted(self):
        r = make_safe("password=supersecret123")
        assert "supersecret123" not in r.safe_prompt


class TestCloudBlockingPrivateMode:
    def test_source_code_blocked_for_cloud_in_private_mode(self):
        code = "import os\ndef main():\n    pass"
        r = make_safe(code, private_mode=True, cloud_target=True)
        assert r.blocked_reason is not None
        assert r.risk_level in ("high", "critical", "blocked")

    def test_source_code_allowed_for_local(self):
        code = "import os\ndef main():\n    pass"
        r = make_safe(code, private_mode=True, cloud_target=False)
        assert r.blocked_reason is None

    def test_plain_text_blocked_for_cloud_in_private_mode(self):
        # private_mode=True blocks ALL cloud calls, not just code
        r = make_safe("Did the login form succeed?", private_mode=True, cloud_target=True)
        assert r.blocked_reason is not None  # private_mode blocks all cloud calls

    def test_stack_trace_blocked_for_cloud_in_private_mode(self):
        trace = "Traceback (most recent call last):\n  File app.py line 10\nValueError: bad"
        r = make_safe(trace, private_mode=True, cloud_target=True)
        assert r.blocked_reason is not None


class TestRedactForLogging:
    def test_api_key_redacted_in_log(self):
        log = redact_for_logging("Bearer sk-abcdefghijklmnopqrstuvwxyz123456")
        assert "sk-abc" not in log

    def test_safe_text_unchanged(self):
        log = redact_for_logging("step 1 passed")
        assert log == "step 1 passed"
