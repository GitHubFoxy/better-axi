# Vendor Dependencies

`better-axi` unites three key systems:
1. **AXI (`chrome-devtools-axi`)**: Node-based tool for token-efficient accessibility snapshotting and actions (click, type, scroll, wait) over Chrome DevTools Protocol (CDP).
   - Upstream repo: `https://github.com/kunchenguid/chrome-devtools-axi.git`
   - Local dotfiles reference: `../chrome-devtools-axi-local/chrome-devtools-axi`
2. **Crawl4AI**: Python-based high-throughput content extraction tool (`fit_markdown`, CSS/XPath schema extraction, batch page downloads) connecting directly to running Helium browser via CDP (`--remote-debugging-port`).
   - Upstream repo: `https://github.com/unclecode/crawl4ai.git`
3. **Jev**: Fast classifier and decision-maker in a tight loop for web navigation and filtering (`Fit` / `50-50` / `Bad`).
   - Local reference: `../chrome-devtools-axi-local/jev-stuff/`

## Setup
Run `./vendor/setup.sh` to initialize submodules or establish symbolic references.
