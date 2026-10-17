# better-axi — Agentic Browser Primitives

Browser navigation, content extraction and fast classification over Chrome DevTools Protocol (CDP), with structured decisions delegated to [Personal AI Gateway (PAG)](https://github.com/GitHubFoxy/personal-ai-gateway).

**Architecture:** Better-AXI owns browser actions and classification semantics. PAG owns model credentials, provider routing, fallback and timeouts. Better-AXI sends one HTTP request per decision; it never calls model providers directly.

## Commands

- nav: autonomous CDP navigation via PAG Decisions.
- extract active: fetch the current browser page using Crawl4AI.
- extract batch: scrape a list of URLs concurrently.
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

export CHROME_DEVTOOLS_AXI_PORT=9335
export CHROME_DEVTOOLS_AXI_BROWSER_URL=http://127.0.0.1:9335
export CHROME_DEVTOOLS_AXI_SESSION=career
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
