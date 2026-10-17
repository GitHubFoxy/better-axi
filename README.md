# better-axi — Agentic Browser Primitives

Browser navigation, content extraction and fast classification over Chrome DevTools Protocol (CDP), with structured decisions delegated to [Personal AI Gateway (PAG)](https://github.com/GitHubFoxy/personal-ai-gateway).

**Architecture:** Better-AXI owns browser actions and classification semantics. PAG owns model credentials, provider routing, fallback and timeouts. Better-AXI sends one HTTP request per decision; it never calls model providers directly.

## Commands

- nav: autonomous CDP navigation via PAG Decisions.
- extract active: read exactly one CDP page; pass `--url` when several page targets are open.
- extract batch: scrape a URL list concurrently through Crawl4AI in the connected browser.
- classify: categorize input items as Fit / 50-50 / Bad with PAG.

~~~sh
./bin/better-axi nav --goal "Search for backend roles"
./bin/better-axi extract active --mode fit_markdown
./bin/better-axi classify --criteria "Remote TypeScript backend" < items.json
~~~

## Installation and configuration

Better-AXI requires Node.js 20+; PAG requires Node.js 22.16+ or Bun. For Crawl4AI, install Python 3.11+ and uv.

~~~sh
git clone https://github.com/GitHubFoxy/better-axi.git
cd better-axi
npm install
uv sync
~~~

Start [PAG](https://github.com/GitHubFoxy/personal-ai-gateway) separately, initialize it, configure a Decisions provider account and route named decision. Then export:

~~~sh
export PAG_BASE_URL=http://127.0.0.1:4000/v1
export PAG_API_KEY=pag_your_local_gateway_key
export PAG_DECISION_MODEL=decision

export CHROME_DEVTOOLS_AXI_SESSION=career

# Chrome DevTools endpoints — two different things, do not point them at each other:
# 1. AXI bridge port: the chrome-devtools-axi process's own channel. Career uses
#    bridge 9445 paired with CDP 9335. Never set this to the CDP port.
export CHROME_DEVTOOLS_AXI_PORT=9445
# 2. CDP endpoint of the Chrome you want to reuse (--remote-debugging-port).
#    Both navigation decisions and `extract` crawling attach to this browser.
#    Without it, `extract` fails fast instead of guessing a port.
export CHROME_DEVTOOLS_AXI_BROWSER_URL=http://127.0.0.1:9335
~~~

PAG_BASE_URL and PAG_DECISION_MODEL are optional (defaults above). PAG_API_KEY is required for real Decisions requests. A ChatGPT Plus subscription does not itself grant native Decisions API access; use a compatible PAG Decisions account. Remote PAG endpoints must use HTTPS.

## Layout

- core/agent/loop.mjs — CDP navigation loop and action mapping.
- core/agent/classifier.mjs — batch decisions and labels.
- core/agent/evaluator.mjs — local vacancy heuristics and cover letters.
- core/pag/client.mjs — thin HTTP client for POST /v1/decisions.
- core/extractor/ — Python Crawl4AI bridge.
- core/workflows/ — HH.ru and Ozon workflow compositions.

No embedded JEV client, no direct provider routing, and no bundled PAG server.

See [PAG integration notes](docs/pag-integration.md) for setup and diagnostics.

## Tests

~~~sh
npm test
uv run pytest
~~~

Node tests use local mock decisions and fetch stubs, so they require no external provider quota.

MIT © [GitHubFoxy](https://github.com/GitHubFoxy).
