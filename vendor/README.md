# Vendor Dependencies

`better-axi` uses three complementary systems:
1. **AXI (`chrome-devtools-axi`)**: Node-based tool for token-efficient accessibility snapshotting and actions (click, type, scroll, wait) over Chrome DevTools Protocol (CDP).
   - Upstream repo: `https://github.com/kunchenguid/chrome-devtools-axi.git`
   - Local dotfiles reference: `../../../pi/agent/skills/chrome-devtools-axi-local/chrome-devtools-axi`
2. **Crawl4AI**: Python-based high-throughput content extraction tool (`fit_markdown`, CSS/XPath schema extraction, batch page downloads) connecting directly to running Helium browser via CDP (`--remote-debugging-port`).
   - Upstream repo: `https://github.com/unclecode/crawl4ai.git`
3. **PAG**: External structured Decisions API for the autonomous browser loop and item classifier.
   - Upstream repo: `https://github.com/GitHubFoxy/personal-ai-gateway`
   - Connection details: `../docs/pag-integration.md`

## Setup
Run `./vendor/setup.sh` to initialize submodules or establish symbolic references.
