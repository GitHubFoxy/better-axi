"""
Ozon Buying Workflow uniting AXI, PAG-backed Decisions, and Crawl4AI.
1. Nav: Search "Туалетная бумага 3 слоя", sort by rating.
2. Extract: Crawl4AI extracts cards across page 1 and page 2.
3. Unit-economics Evaluation: Exclude forbidden vendors (Yandex Fabrika, Tuvio),
   calculate price-per-roll / best value.
4. Selection & Action: Report winner + 2 alternatives, add to cart upon confirmation.
"""
from __future__ import annotations

import asyncio
import json
import urllib.parse
from typing import Any, Callable, Dict, List, Optional

from core.extractor.bridge import Crawl4AIBridge
from core.extractor.schemas import OzonProductRecord


class OzonBuyerWorkflow:
    """Executes Ozon search, multi-page extraction, unit-economics scoring, and cart action."""

    FORBIDDEN_VENDORS_DEFAULT = ["Yandex Fabrika", "Яндекс Фабрика", "Tuvio"]

    def __init__(
        self,
        extractor: Optional[Crawl4AIBridge] = None,
        cart_action_fn: Optional[Callable[[str], Any]] = None,
        forbidden_vendors: Optional[List[str]] = None,
    ):
        self.extractor = extractor or Crawl4AIBridge()
        self.cart_action_fn = cart_action_fn
        self.forbidden_vendors = forbidden_vendors or list(self.FORBIDDEN_VENDORS_DEFAULT)

    def build_search_url(self, query: str = "Туалетная бумага 3 слоя", page: int = 1) -> str:
        """Construct Ozon search URL with query, sorting by rating, and page number."""
        encoded_query = urllib.parse.quote(query)
        base = f"https://www.ozon.ru/search/?text={encoded_query}&sorting=rating"
        return f"{base}&page={page}" if page > 1 else base

    async def run(
        self,
        query: str = "Туалетная бумага 3 слоя",
        pages: int = 2,
        confirm_add_to_cart: bool = False,
        mock_pages_html: Optional[Dict[int, str]] = None,
    ) -> Dict[str, Any]:
        """Execute the full Ozon evaluation pipeline across multiple pages."""
        all_products: List[OzonProductRecord] = []

        # Step 1 & 2: Nav and multi-page extract
        for p in range(1, pages + 1):
            if mock_pages_html and p in mock_pages_html:
                prods = self.extractor.parse_ozon_search_html(mock_pages_html[p], page_num=p)
            else:
                url = self.build_search_url(query, page=p)
                crawl_res = await self.extractor.crawl_url(url)
                prods = self.extractor.parse_ozon_search_html(crawl_res.get("html", ""), page_num=p)
            all_products.extend(prods)

        if not all_products:
            return {"status": "empty", "products_found": 0, "message": "No products extracted."}

        # Step 3: Unit-economics evaluation & vendor filtering
        eligible_products: List[OzonProductRecord] = []
        rejected_products: List[Dict[str, Any]] = []

        for prod in all_products:
            prod.compute_economics(forbidden_vendors=self.forbidden_vendors)
            if prod.is_forbidden_vendor:
                rejected_products.append({
                    "id": prod.id,
                    "title": prod.title,
                    "vendor": prod.vendor,
                    "reason": "Forbidden vendor restriction",
                })
            elif prod.layer_count != 3 and "3 слоя" in query:
                rejected_products.append({
                    "id": prod.id,
                    "title": prod.title,
                    "reason": f"Mismatched layer count: {prod.layer_count} instead of 3",
                })
            else:
                eligible_products.append(prod)

        # Sort by best value score descending (or price_per_roll ascending)
        eligible_products.sort(key=lambda x: (x.value_score, -x.price_per_roll), reverse=True)

        winner = eligible_products[0] if eligible_products else None
        alternatives = eligible_products[1:3] if len(eligible_products) > 1 else []

        # Step 4: Selection & Action
        cart_result = None
        if winner and confirm_add_to_cart and self.cart_action_fn:
            cart_result = self.cart_action_fn(winner.url or winner.id)

        return {
            "status": "success",
            "query": query,
            "pages_scanned": pages,
            "total_extracted": len(all_products),
            "eligible_count": len(eligible_products),
            "forbidden_or_rejected": len(rejected_products),
            "winner": winner.model_dump() if winner else None,
            "alternatives": [a.model_dump() for a in alternatives],
            "cart_action_executed": cart_result is not None,
            "cart_result": cart_result,
            "report": {
                "winner_summary": (
                    f"🏆 WINNER: {winner.title}\n"
                    f"   Price: {winner.price} ₽ | Rolls: {winner.rolls_count} | Price/roll: {winner.price_per_roll} ₽\n"
                    f"   Rating: {winner.rating} ★ ({winner.reviews_count} reviews) | Seller: {winner.vendor or 'N/A'}\n"
                    f"   Value Score: {winner.value_score}"
                ) if winner else "No eligible winner found.",
                "alternatives_summary": [
                    f"🥈 ALT #{i+1}: {alt.title} — {alt.price} ₽ ({alt.price_per_roll} ₽/рул), {alt.rating} ★"
                    for i, alt in enumerate(alternatives)
                ],
            },
        }


if __name__ == '__main__':
    import sys
    workflow = OzonBuyerWorkflow()
    query = sys.argv[1] if len(sys.argv) > 1 else 'Туалетная бумага 3 слоя'
    pages = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    res = asyncio.run(workflow.run(query=query, pages=pages))
    print(json.dumps(res, ensure_ascii=False, indent=2))
