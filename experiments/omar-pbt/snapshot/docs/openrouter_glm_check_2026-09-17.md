# OpenRouter GLM connectivity check — 17 September 2026

The live OpenRouter models catalog listed `z-ai/glm-5.2:free` with zero input/output token pricing. It also listed GLM 5.3 paid variants, but no GLM 5.3 free variant in the inspected catalog.

One authenticated request to `/api/v1/chat/completions` requested `z-ai/glm-5.2:free`, the message `Reply with exactly OK.`, and 128 maximum output tokens. Provider fallbacks were disabled and maximum prompt/completion prices were both zero. The locally configured credential was used without placing it in any artifact.

Result: HTTP 429. Provider Decart reported `overloaded`, with limit source `upstream_provider_shared_pool` and a five-second retry hint. This is evidence that this request could not obtain a response, not that the model never works or that the API key is invalid. No model completion was obtained, no paid alternative was selected, and no GLM experiment was launched. A later availability check or a separately supplied provider key is needed before a GLM replication.

Catalog: https://openrouter.ai/api/v1/models

GLM 5.2 and GLM 5.3 are distinct model conditions. A successful GLM 5.2 free run would not fulfill an exact GLM 5.3 replication.
