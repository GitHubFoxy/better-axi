---
name: better-axi
description: Modular agentic browser building blocks uniting AXI, Jev fast loop, and Crawl4AI over shared CDP. Use to compose any browser workflow on the fly.
---

# better-axi — Modular Browser Building Blocks

`better-axi` provides **atomic primitives** for AI agents to compose arbitrary browser workflows instead of relying on brittle hardcoded scripts.

It operates over a running **Helium / Chrome** browser with Chrome DevTools Protocol (CDP) enabled (`--remote-debugging-port=$PORT`).

---

## 🧱 The 3 Building Blocks

| Block | Command | What it does | When to use |
| :--- | :--- | :--- | :--- |
| **1. Fast Nav Loop** | `better-axi nav --goal "..."` | Runs a sub-second **Jev autonomous loop** over CDP until the goal is visibly achieved (`status: done`) or intervention is needed (`status: handoff`). | Navigating to pages, typing into search bars, applying UI filters, opening accordions. |
| **2. Clean Extractor** | `better-axi extract active` / `batch` | Connects **Crawl4AI** to the browser over CDP to extract `fit_markdown` (80% noise stripped) or fetch 20 URLs in the background. | Reading search results, catalog listings, or scraping full vacancy descriptions. |
| **3. Fast Classifier** | `better-axi classify --criteria "..."` | High-throughput semantic filtering (`Fit` / `50-50` / `Bad`) using fast decision models. | Screening 50+ items at low cost before deep investigation. |
| **4. Raw Interactive AXI** | `npx -y chrome-devtools-axi <action>` | Direct single-action execution: `open`, `snapshot`, `click <uid>`, `fill <uid>`, `press`. | Final single-click actions (e.g. clicking "Add to Cart" or "Apply") or human inspection. |

For `extract active`, the extractor requires exactly one page target or an exact URL via `--url`; it fails closed on ambiguous targets. HH search parsing returns only scoped result cards and does not treat arbitrary vacancy links as results.

---

## 🛠 Composing Workflows (How to Think)

As an LLM agent, do not write custom browser scrapers from scratch. Compose the building blocks:

```text
User Request ("Buy X on Store Y", "Find jobs matching my resume")
       │
       ▼
[ Step 1: Nav ]     ──►  better-axi nav --goal "Search for X and apply filters"
       │
       ▼
[ Step 2: Extract ] ──►  better-axi extract active --mode fit_markdown
       │
       ▼
[ Step 3: Reason ]  ──►  LLM calculates unit economics, ranks choices, picks winner
       │
       ▼
[ Step 4: Act ]     ──►  npx -y chrome-devtools-axi click <winner_button_uid>
```

---

## ⚙️ Environment & CDP Profiles

Always select the correct browser profile:
- **Shopping / Marketplaces**: Ozon Profile (`~/Library/Application Support/Helium-AXI/Ozon`, port `9336`).
- **Jobs / Telegram / Work**: Career Profile (`~/Library/Application Support/Helium-AXI/Career`, port `9335`).
- **Personal Profile**: NEVER touch or attach automation to the user's primary profile.

```bash
export CHROME_DEVTOOLS_AXI_PORT=9336
export CHROME_DEVTOOLS_AXI_BROWSER_URL="http://127.0.0.1:9336"
export CHROME_DEVTOOLS_AXI_SESSION="ozon"
```
