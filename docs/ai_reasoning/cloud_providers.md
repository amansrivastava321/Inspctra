# Optional cloud models: Gemini and Groq

By default QA-AI uses local models through Ollama and sends nothing off the machine. You can add two
cloud providers on top. They are advisory helpers (root-cause notes, test-plan drafts, report
synthesis); verdicts always come from deterministic checks.

| Provider | Default model | Good for |
|---|---|---|
| Gemini (Google AI Studio) | `gemini-2.5-pro` | Hard reasoning, long context |
| Groq | `llama-3.3-70b-versatile` | Fast, cheap, high-volume tasks |

## Turning it on

Cloud use needs **all three** of these. Missing any one keeps everything local:

1. A key for at least one provider (see below).
2. `QA_AI_ALLOW_CLOUD_MODELS=true`
3. `QA_AI_MODEL_ROUTING_MODE=specialist_cloud_first`

| Setting | Accepted names |
|---|---|
| Gemini key | `QA_AI_GEMINI_API_KEY`, `GEMINI_API_KEY`, or `GOOGLE_API_KEY` |
| Groq key | `QA_AI_GROQ_API_KEY` or `GROQ_API_KEY` |
| Model override | `QA_AI_GEMINI_MODEL`, `QA_AI_GROQ_MODEL` |
| Endpoint override | `QA_AI_GEMINI_BASE_URL`, `QA_AI_GROQ_BASE_URL` (any OpenAI-compatible `/chat/completions` API) |
| Timeout (seconds) | `QA_AI_GEMINI_TIMEOUT_SECONDS` (default 120), `QA_AI_GROQ_TIMEOUT_SECONDS` (default 45) |

Keep keys in environment variables or an untracked `.env` file (`.env` is gitignored). Never commit
them and never paste them into chats, issues or logs. Key values are never written to reports.

## How requests are routed

Providers that have a key are tried in this order, then any configured OpenRouter models, then your
local model, then the deterministic fallback:

- Reasoning-heavy components (orchestration, repo reasoning, structured reasoning, long strategy):
  Gemini, then Groq.
- Report synthesis: Groq, then Gemini (speed first).
- Embeddings and visual analysis never use these providers.

If a provider is rate limited, down or returns something unusable, the next one is tried.

## Privacy

Cloud providers receive whatever prompt the calling feature builds, so only enable them for code and
evidence you are allowed to share.

- **Private-code mode** (`QA_AI_PRIVATE_CODE_MODE=true`, or code the audit marks private): only a
  redacted summary is sent to cloud providers, never the raw prompt (on by default; controlled by
  `QA_AI_REDACT_CLOUD_CONTEXT`).
- **Credentials are always stripped.** Every prompt the router sends to a cloud provider (OpenRouter,
  Gemini or Groq) first goes through `redact_secrets`, which replaces API keys (including Google
  `AIza…` and Groq `gsk_…` formats), bearer tokens, JWTs, private key blocks, database URLs with
  credentials and `password=` values with placeholders. It changes nothing else: no truncation, no
  blocking, and commit hashes and digests are left alone. Local (Ollama) prompts are not redacted.
- **With private-code mode off**, everything else in the prompt is sent as the calling feature built
  it. Redaction recognises known credential formats, so it is a safety net and not a guarantee: an
  unusual secret format, or proprietary code, would still be sent.
- Embeddings and visual analysis never go to cloud providers.
- Free tiers can have different data-use terms from paid tiers. Read the provider's terms before
  sending client or proprietary code.

## Checking the setup

```bash
python -m qa_ai.cli models doctor
```

Shows which providers are configured, the routing mode, and the model chosen for a sample request.
