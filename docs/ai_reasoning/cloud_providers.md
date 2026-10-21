# Optional cloud models: Gemini and Groq

By default QA-AI uses local models through Ollama and sends nothing off the machine. You can add two
cloud providers on top. They are advisory helpers (root-cause notes, test-plan drafts, report
synthesis); verdicts always come from deterministic checks.

| Provider | Default model | Good for |
|---|---|---|
| Gemini (Google AI Studio) | `gemini-3.8-flash` | Fast reasoning and coding, 1M-token context |
| Groq | `openai/gpt-oss-120b` | Strong open reasoning and coding model, fast |

Both defaults are available on the providers' free tiers. Providers retire models, so these names
can go out of date: if a call fails with a 404 "model not found", list what your key can use
(`GET <base_url>/models`) and set `QA_AI_GEMINI_MODEL` / `QA_AI_GROQ_MODEL`.

### Free-tier limits (approximate, set by the providers and subject to change)

| Provider | Model | Limits |
|---|---|---|
| Gemini | `gemini-3.8-flash` | about 10 requests/min, about 1,500/day |
| Groq | `openai/gpt-oss-120b` | about 30 requests/min, 1,000/day, 8,000 tokens/min, 200,000 tokens/day |

Check your account's live limits in Google AI Studio and the Groq console. Limits apply per account,
not per key. A rate-limited call is not retried: the router moves on to the next provider
(Gemini, then Groq, then OpenRouter, then the local model, then the deterministic fallback).

**Privacy on free tiers:** Google may use prompts and responses from the free Gemini tier to improve
its models, and human reviewers may read them. Do not send confidential or proprietary code through
a free Gemini key; keep private-code mode on for such code.

## Turning it on

Cloud use needs **all three** of these. Missing any one keeps everything local:

1. A key for at least one provider (see below).
2. `QA_AI_ALLOW_CLOUD_MODELS=true`
3. `QA_AI_MODEL_ROUTING_MODE=specialist_cloud_first`

| Setting | Accepted names |
|---|---|
| Gemini key | `QA_AI_GEMINI_API_KEY`, `GEMINI_API_KEY`, or `GOOGLE_API_KEY` |
| Groq key | `QA_AI_GROQ_API_KEY` or `GROQ_API_KEY` |
| Model override | `QA_AI_GEMINI_MODEL`, `QA_AI_GROQ_MODEL`, `QA_AI_GEMINI_FALLBACK_MODEL` (backup Gemini model, default `gemini-3.5-flash-lite`) |
| Endpoint override | `QA_AI_GEMINI_BASE_URL`, `QA_AI_GROQ_BASE_URL` (any OpenAI-compatible `/chat/completions` API) |
| Timeout (seconds) | `QA_AI_GEMINI_TIMEOUT_SECONDS` (default 120), `QA_AI_GROQ_TIMEOUT_SECONDS` (default 45) |

### Where to put the keys

Either set them as environment variables in the shell that starts the backend, or use a `.env` file:

```bash
cp .env.example .env      # then edit .env and fill in the values you need
```

- `.env` lives in the project root, is gitignored and is never committed. `.env.example` is the
  committed template and must stay free of real values.
- Variables already set in your shell win over `.env`.
- Only `QA_AI_*`, `INSPECTRA_*`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `GROQ_API_KEY` and
  `OPENROUTER_API_KEY` are read from the file. Only the project root is searched, never the current
  directory, so auditing another app does not pick up that app's `.env`.
- Set `INSPECTRA_DISABLE_DOTENV=1` to ignore the file.

Never commit keys and never paste them into chats, issues or logs. Key values are never written to
reports.

## Which features use the cloud models

| Feature | Cloud models | Otherwise |
|---|---|---|
| Root-cause suggestions (live run) | Yes, when a provider is configured and private-code mode is not withholding the prompt | Local Ollama model, then built-in logic |
| Evidence evaluation (live run) | Same as above | Same as above |
| Test plan "Generate with AI" | **No, local Ollama only** | Built-in logic (`Source: local_fallback`) |

For the first two, the response's `generation_source` names whoever answered (`gemini`, `groq`, `openrouter`,
`ollama`) or `local_fallback`. They do not require Ollama when a cloud provider will answer. When the
local model is the one answering, they still check first that it is ready, and fall back to the
built-in logic if it is not (the default model is `qwen3.5:9b`; install it with `ollama pull qwen3.5:9b`).

Private-code mode (`QA_AI_PRIVATE_CODE_MODE=true`) sends cloud models only a redacted placeholder, so these
features treat the cloud as unavailable while it is on.

## How requests are routed

Providers that have a key are tried in this order, then any configured OpenRouter models, then your
local model, then the deterministic fallback:

- Reasoning-heavy components (orchestration, repo reasoning, structured reasoning, long strategy):
  Gemini (`gemini-3.8-flash`), then Groq, then the lighter Gemini backup (`gemini-3.5-flash-lite`).
- Report synthesis: Groq, then Gemini, then the Gemini backup (speed first).
- Embeddings and visual analysis never use these providers.

If a provider is rate limited, down or returns something unusable, the next one is tried. The Gemini
backup exists because a busy Gemini model answers 503 "high demand" while a lighter one often still
answers; it uses a separate model name, so set `QA_AI_GEMINI_FALLBACK_MODEL` if it is retired.

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

### Seeing why a provider was skipped

The routed result lists every provider tried, in order, with `ok` or the failure reason (for example
`http_401`, `http_404`, `provider_unavailable`, `rate_limited`). Message text is never included.

```python
from qa_ai.ai.model_router import ModelRouter
from qa_ai.ai.model_profiles import RoutingComponent

r = ModelRouter().route(RoutingComponent.STRUCTURED_REASONING, "Reply with exactly one word: pong", {})
print(r.provider, r.model)
for attempt in r.attempts:
    print(attempt)
```
