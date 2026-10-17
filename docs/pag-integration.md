# Better-AXI ↔ Personal AI Gateway (PAG)

Better-AXI delegates all structured model decisions to PAG; the browser loop, extraction and decision consumers remain in Better-AXI. Provider configuration and fallback live only in PAG.

## Start PAG

See [PAG Decisions API documentation](https://github.com/GitHubFoxy/personal-ai-gateway/blob/main/docs/decisions.md).

~~~sh
cd personal-ai-gateway
npm run pag -- init
# Configure a real Decisions account and its upstream credentials.
# Use actual available account and model identifiers:
npm run pag -- route set decision decisions my-account:my-model
npm start
~~~

Store the one-time local gateway key securely, then connect Better-AXI:

~~~sh
export PAG_BASE_URL=http://127.0.0.1:4000/v1
export PAG_API_KEY=pag_your_local_key
export PAG_DECISION_MODEL=decision
~~~

Only the PAG gateway key belongs in Better-AXI. Configure provider keys and upstream routing in PAG. A ChatGPT Plus subscription by itself does not support native Decisions API requests.

## Wire contract

Better-AXI submits one POST /v1/decisions request per decision in the System One-compatible shape:

~~~json
{
  "model": "decision",
  "state": { "page": { "text": "..." } },
  "questions": {
    "operation": {
      "type": "choice",
      "instructions": "Choose the next action",
      "criteria": { "CLICK": "Click an observed element", "DONE": "Goal achieved" }
    }
  }
}
~~~

PAG responds with named answers, optionally usage data, and provider metadata in x-pag-provider and x-pag-model headers. The local adapter validates choices and returns the existing Better-AXI response shape.

PAG choice IDs support alphanumeric, underscore, hyphen and dot characters, unlike AXI action IDs (CLICK:42). The navigation loop maps opaque AXI IDs to safe target_N choices before the call, and maps the selected choice back before acting. PAG requires two or more options for a choice question; a single available target is selected locally.

## Live workflow and tests

Better-AXI nav and classify use PAG directly. Live HH.ru job-search workflows delegate classification through the Node runner to the same PAG adapter. The Python workflow retains deterministic local classification only for supplied HTML fixtures; callers may inject a classifier for tests.

~~~sh
npm test
uv run pytest
~~~

Tests use mock decisions and stub HTTP responses; live provider access is not required.

## Troubleshooting

- PAG_API_KEY missing: set the locally generated gateway key.
- HTTP 401: the local PAG API key is invalid.
- HTTP 422: the alias, route family, instructions or choices are incompatible.
- HTTP 503 / 504: PAG has no successful Decisions route or its deadline expired; inspect PAG server logs and run pag status.
- ECONNREFUSED: start PAG and verify the base URL.
- For remote PAG, use HTTPS. Plain HTTP is accepted only on loopback.
- Legacy OPENROUTER_API_KEY, AI_GATEWAY_API_KEY and CLOUDFLARE_API_TOKEN are ignored by Better-AXI.
