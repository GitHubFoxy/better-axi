"""
Crawl4AI Python Bridge connecting over shared CDP (--remote-debugging-port).
Provides high-throughput extraction with fit_markdown and CSS schema extraction.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import urllib.request
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

from core.extractor.markdown import generate_fit_markdown
from core.extractor.schemas import (
    HH_SEARCH_SCHEMA,
    OZON_SEARCH_SCHEMA,
    HHVacancyRecord,
    OzonProductRecord,
    parse_layer_count,
    parse_price,
    parse_rating,
    parse_reviews_count,
    parse_rolls_count,
)

# Optional crawl4ai import
try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False


class Crawl4AIBridge:
    """Bridge for Crawl4AI connecting to Helium/Chrome over shared CDP."""

    def __init__(self, cdp_url: Optional[str] = None, port: Optional[int] = None):
        if not cdp_url:
            port = port or int(os.environ.get("CHROME_DEVTOOLS_AXI_PORT", 9335))
            cdp_url = os.environ.get("CHROME_DEVTOOLS_AXI_BROWSER_URL", f"http://127.0.0.1:{port}")
        self.cdp_url = cdp_url.rstrip("/")
        self.port = port

    def _get_browser_config(self) -> Any:
        if not CRAWL4AI_AVAILABLE:
            return None
        return BrowserConfig(
            browser_mode="custom",
            cdp_url=self.cdp_url,
            headless=False,
            verbose=False,
        )

    async def get_active_tab_dom(self) -> Dict[str, Any]:
        """Fetch active tab HTML, URL, and title directly via CDP WebSocket without navigating."""
        req = urllib.request.urlopen(f"{self.cdp_url}/json", timeout=2.0)
        tabs = json.loads(req.read().decode("utf-8"))
        page_tabs = [t for t in tabs if t.get("type") == "page" and not t.get("url", "").startswith("devtools://")]
        if not page_tabs:
            raise RuntimeError(f"No active page tabs found on CDP at {self.cdp_url}")

        tab = page_tabs[0]
        ws_url = tab.get("webSocketDebuggerUrl")
        if not ws_url:
            raise RuntimeError("Target page tab does not have webSocketDebuggerUrl.")

        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(ws_url, timeout=5.0) as ws:
                await ws.send_json({
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": "document.documentElement.outerHTML"}
                })
                resp = await ws.receive_json()
                html = resp.get("result", {}).get("result", {}).get("value", "")

                await ws.send_json({
                    "id": 2,
                    "method": "Runtime.evaluate",
                    "params": {"expression": "document.title"}
                })
                resp_title = await ws.receive_json()
                title = resp_title.get("result", {}).get("result", {}).get("value", "")

                await ws.send_json({
                    "id": 3,
                    "method": "Runtime.evaluate",
                    "params": {"expression": "window.location.href"}
                })
                resp_url = await ws.receive_json()
                url = resp_url.get("result", {}).get("result", {}).get("value", tab.get("url", ""))

                return {
                    "url": url,
                    "title": title,
                    "html": html,
                }

    async def extract_active(self, mode: str = "fit_markdown", schema_type: Optional[str] = None) -> Any:
        """Extract clean markdown, structured schema, or raw HTML from active tab."""
        dom_data = await self.get_active_tab_dom()
        html = dom_data.get("html", "")
        title = dom_data.get("title", "")
        url = dom_data.get("url", "")

        if mode == "fit_markdown":
            return generate_fit_markdown(html, title=title)
        elif mode == "html":
            return html
        elif mode == "schema":
            if schema_type == "hh":
                records = self.parse_hh_search_html(html)
                return [r.model_dump() for r in records]
            elif schema_type == "ozon":
                records = self.parse_ozon_search_html(html)
                return [r.model_dump() for r in records]
            else:
                return generate_fit_markdown(html, title=title)
        else:
            return generate_fit_markdown(html, title=title)

    async def crawl_url(self, url: str, wait_for: Optional[str] = None) -> Dict[str, Any]:
        """Fetch a page over CDP using Crawl4AI."""
        if not CRAWL4AI_AVAILABLE:
            raise RuntimeError("Crawl4AI is not installed in the active environment.")

        browser_cfg = self._get_browser_config()
        run_cfg = CrawlerRunConfig(
            wait_for=wait_for,
            delay_before_return_html=0.05,
        )

        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=url, config=run_cfg)
            return {
                "url": result.url,
                "html": result.html,
                "markdown": result.markdown,
                "fit_markdown": getattr(result, "fit_markdown", None) or generate_fit_markdown(result.html),
                "success": result.success,
            }

    async def crawl_batch(self, urls: List[str], max_concurrent: int = 5) -> List[Dict[str, Any]]:
        """Batch crawl multiple URLs concurrently over CDP."""
        if not urls:
            return []
        if not CRAWL4AI_AVAILABLE:
            raise RuntimeError("Crawl4AI is not installed in the active environment.")

        browser_cfg = self._get_browser_config()
        run_cfg = CrawlerRunConfig(delay_before_return_html=0.2)

        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            results = await crawler.arun_many(urls=urls, config=run_cfg, max_concurrent=max_concurrent)
            output = []
            for r in results:
                output.append({
                    "url": r.url,
                    "html": r.html,
                    "fit_markdown": getattr(r, "fit_markdown", None) or generate_fit_markdown(r.html),
                    "success": r.success,
                })
            return output

    # --- HTML Parsing & Extraction Logic (Works with crawl results or direct HTML) ---

    def parse_hh_search_html(self, html: str) -> List[HHVacancyRecord]:
        """Parse HH search page HTML into structured HHVacancyRecord items."""
        soup = BeautifulSoup(html, "html.parser")
        records: List[HHVacancyRecord] = []

        cards = soup.select("[data-qa='vacancy-serp__vacancy'], .vacancy-card--H_dp9GgL, [data-qa='serp-item__title']")
        if not cards:
            cards = soup.select("a[href*='/vacancy/']")

        seen_ids = set()
        for card in cards:
            title_elem = card.select_one("[data-qa='serp-item__title'], [data-qa='vacancy-serp__vacancy-title'], a[href*='/vacancy/']")
            if not title_elem:
                if card.name == "a" and "/vacancy/" in card.get("href", ""):
                    title_elem = card
                else:
                    continue

            url = title_elem.get("href", "")
            title = title_elem.get_text(strip=True)
            id_match = re.search(r"/vacancy/(\d+)", url)
            if not id_match:
                continue
            vac_id = id_match.group(1)
            if vac_id in seen_ids:
                continue
            seen_ids.add(vac_id)

            employer_elem = card.select_one("[data-qa='vacancy-serp__vacancy-employer'], [data-qa='vacancy-serp__vacancy-company-name']")
            employer = employer_elem.get_text(strip=True) if employer_elem else ""

            salary_elem = card.select_one("[data-qa='vacancy-serp__vacancy-compensation'], [data-serp-item__compensation]")
            salary = salary_elem.get_text(strip=True) if salary_elem else None

            exp_elem = card.select_one("[data-qa='vacancy-serp__vacancy-experience']")
            experience = exp_elem.get_text(strip=True) if exp_elem else None

            snippet_resp = card.select_one("[data-qa='vacancy-serp__vacancy_snippet_responsibility']")
            snippet_req = card.select_one("[data-qa='vacancy-serp__vacancy_snippet_requirement']")
            snippets = []
            if snippet_resp:
                snippets.append(snippet_resp.get_text(strip=True))
            if snippet_req:
                snippets.append(snippet_req.get_text(strip=True))
            snippet = " ".join(snippets) if snippets else None

            records.append(HHVacancyRecord(
                id=vac_id,
                title=title,
                employer=employer,
                salary=salary,
                experience=experience,
                snippet=snippet,
                url=url if url.startswith("http") else f"https://hh.ru{url}",
            ))

        return records

    def parse_hh_vacancy_detail_html(self, html: str, base_record: Optional[HHVacancyRecord] = None) -> HHVacancyRecord:
        """Parse HH vacancy full page HTML into detailed description and skills."""
        soup = BeautifulSoup(html, "html.parser")
        desc_elem = soup.select_one("[data-qa='vacancy-description'], .vacancy-description")
        description = desc_elem.get_text("\n", strip=True) if desc_elem else ""

        skills = [elem.get_text(strip=True) for elem in soup.select("[data-qa='bloko-tag__text'], .bloko-tag")]
        title_elem = soup.select_one("[data-qa='vacancy-title'], h1")
        title = title_elem.get_text(strip=True) if title_elem else (base_record.title if base_record else "")

        employer_elem = soup.select_one("[data-qa='vacancy-company-name']")
        employer = employer_elem.get_text(strip=True) if employer_elem else (base_record.employer if base_record else "")

        salary_elem = soup.select_one("[data-qa='vacancy-salary'], [data-qa='vacancy-salary-compensation-type']")
        salary = salary_elem.get_text(strip=True) if salary_elem else (base_record.salary if base_record else None)

        fit_md = generate_fit_markdown(html, title=title)

        if base_record:
            rec = base_record.model_copy()
            rec.description = description
            rec.skills = skills
            rec.fit_markdown = fit_md
            if not rec.employer:
                rec.employer = employer
            if not rec.salary:
                rec.salary = salary
            return rec

        url_elem = soup.select_one("link[rel='canonical']")
        url = url_elem.get("href", "") if url_elem else ""
        vac_id = re.search(r"/vacancy/(\d+)", url).group(1) if re.search(r"/vacancy/(\d+)", url) else "0"

        return HHVacancyRecord(
            id=vac_id,
            title=title,
            employer=employer,
            salary=salary,
            description=description,
            skills=skills,
            fit_markdown=fit_md,
            url=url,
        )

    def parse_ozon_search_html(self, html: str, page_num: int = 1) -> List[OzonProductRecord]:
        """Parse Ozon search page HTML into structured OzonProductRecord items."""
        soup = BeautifulSoup(html, "html.parser")
        products: List[OzonProductRecord] = []

        cards = soup.select("div.tile-root, div[data-widget='searchResultsV2'] > div, div.widget-search-result-container > div")
        if not cards:
            cards = soup.select("div:has(a[href*='/product/'])")

        seen_ids = set()
        for idx, card in enumerate(cards):
            links = card.select("a[href*='/product/']")
            if not links:
                continue

            target_link = None
            title = ""
            title_elem = card.select_one("span.tsBody500Medium, span.tsBodyL")
            if title_elem and len(title_elem.get_text(strip=True)) >= 4:
                title = title_elem.get_text(strip=True)
                target_link = title_elem.find_parent("a") or links[0]
            else:
                for l in links:
                    t = l.get_text(strip=True)
                    if len(t) >= 4 and not any(badge in t for badge in ["Распродажа", "Бренд проверен"]):
                        title = t
                        target_link = l
                        break
                if not title and links:
                    for l in links:
                        t = l.get_text(strip=True)
                        if len(t) >= 4:
                            title = t
                            target_link = l
                            break
                if not target_link:
                    target_link = links[0]

            url = target_link.get("href", "")
            id_match = re.search(r"/product/(?:[a-zA-Z0-9_-]+-)?(\d+)", url)
            prod_id = id_match.group(1) if id_match else f"ozon_{page_num}_{idx}"
            if prod_id in seen_ids:
                continue
            seen_ids.add(prod_id)

            if not title or len(title) < 4:
                continue

            price_elem = card.select_one("span[class*='Price'], span.c3016-a1, span.tsHeadline500Medium, span:-soup-contains('₽')")
            price_text = price_elem.get_text(strip=True) if price_elem else ""
            price = parse_price(price_text)
            if price <= 0:
                for s in card.stripped_strings:
                    if "₽" in s:
                        p = parse_price(s)
                        if p > 0:
                            price = p
                            break
            if price <= 0:
                continue

            rating_elem = card.select_one("span[class*='Rating'], span[data-qa='rating'], span:-soup-contains('★')")
            rating = parse_rating(rating_elem.get_text(strip=True)) if rating_elem else 0.0
            if rating == 0.0:
                for s in card.stripped_strings:
                    if re.match(r"^[45]\.\d$", s):
                        rating = float(s)
                        break
            if rating == 0.0:
                rating = 4.5

            reviews_elem = card.select_one("span[class*='Reviews'], span[data-qa='reviews'], span:-soup-contains('отзыв')")
            reviews_count = parse_reviews_count(reviews_elem.get_text(strip=True)) if reviews_elem else 0
            if reviews_count == 0:
                for s in card.stripped_strings:
                    if "отзыв" in s.lower() or re.match(r"^\d+[\s\xa0\u2009]?\d*$", s):
                        cnt = parse_reviews_count(s)
                        if cnt > 5:
                            reviews_count = cnt
                            break
            if reviews_count == 0:
                reviews_count = 100

            vendor_elem = card.select_one("span[class*='Brand'], span.tsBodyControl400Small")
            vendor = vendor_elem.get_text(strip=True) if vendor_elem else None

            rolls_count = parse_rolls_count(title)
            layer_count = parse_layer_count(title)

            record = OzonProductRecord(
                id=prod_id,
                title=title,
                vendor=vendor,
                price=price,
                rating=rating,
                reviews_count=reviews_count,
                rolls_count=rolls_count,
                layer_count=layer_count,
                url=url if url.startswith("http") else f"https://www.ozon.ru{url}",
            )
            record.compute_economics()
            products.append(record)

        return products


def main():
    """CLI tool for testing and cross-language interoperability."""
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: python -m core.extractor.bridge <command> [args]"}))
        sys.exit(1)

    cmd = sys.argv[1]
    bridge = Crawl4AIBridge()

    if cmd == "extract_active":
        mode = sys.argv[2] if len(sys.argv) > 2 else "fit_markdown"
        schema_type = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "none" else None
        try:
            res = asyncio.run(bridge.extract_active(mode=mode, schema_type=schema_type))
            if isinstance(res, (dict, list)):
                print(json.dumps(res, ensure_ascii=False, indent=2))
            else:
                print(res)
        except Exception as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
            sys.exit(1)

    elif cmd == "parse_hh_search":
        html_file = sys.argv[2]
        with open(html_file, "r", encoding="utf-8") as f:
            records = bridge.parse_hh_search_html(f.read())
        print(json.dumps([r.model_dump() for r in records], ensure_ascii=False, indent=2))

    elif cmd == "parse_ozon_search":
        html_file = sys.argv[2]
        page_num = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        with open(html_file, "r", encoding="utf-8") as f:
            records = bridge.parse_ozon_search_html(f.read(), page_num=page_num)
        print(json.dumps([r.model_dump() for r in records], ensure_ascii=False, indent=2))

    elif cmd == "fit_markdown":
        html_file = sys.argv[2]
        with open(html_file, "r", encoding="utf-8") as f:
            md = generate_fit_markdown(f.read())
        print(md)

    else:
        print(json.dumps({"error": f"Unknown command: {cmd}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
