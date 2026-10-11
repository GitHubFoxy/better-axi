"""Data models and extraction schemas for HH.ru and Ozon."""
from __future__ import annotations

import re
from typing import List, Optional
from pydantic import BaseModel, Field


def parse_price(text: Optional[str]) -> float:
    """Parse price string like '1 299 ₽', '1299 ₽', or '1299' into float."""
    if not text:
        return 0.0
    # Remove non-breaking spaces, thin spaces, currency symbols
    cleaned = re.sub(r"[^\d,\.]", "", text.replace(" ", "").replace("\xa0", "").replace("\u2009", ""))
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def parse_reviews_count(text: Optional[str]) -> int:
    """Parse reviews count string like '2 419 отзывов' or '15' into int."""
    if not text:
        return 0
    cleaned = re.sub(r"[^\d]", "", text)
    try:
        return int(cleaned) if cleaned else 0
    except ValueError:
        return 0


def parse_rating(text: Optional[str]) -> float:
    """Parse rating string like '4.9' or '4,8' into float."""
    if not text:
        return 0.0
    m = re.search(r"(\d+[\.,]\d+|\d+)", text)
    if not m:
        return 0.0
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return 0.0


def parse_rolls_count(text: str) -> int:
    """Extract number of rolls, handling multipacks and excluding wet wipes."""
    if not text:
        return 1

    # Wet wipes check: not traditional toilet paper rolls
    if re.search(r"влажн(?:ая|ые|ую|ой)", text, re.IGNORECASE):
        return 1

    # Check multipack multipliers: e.g. '8 рулонов x 2 шт' or '2 пачки по 8 рулонов'
    multipack_patterns = [
        r"(\d+)\s*(?:рул|шт)[^\d]{1,10}(?:х|x|\*)\s*(\d+)\s*(?:пач|упак|шт)?",
        r"(\d+)\s*(?:пач(?:ка|ки|ек)?|упак(?:овка|овки|овок)?)[^\d]{1,10}(?:по|х|x|\*)\s*(\d+)\s*(?:рул|шт)",
    ]
    for mpat in multipack_patterns:
        m = re.search(mpat, text, re.IGNORECASE)
        if m:
            try:
                p1 = int(m.group(1))
                p2 = int(m.group(2))
                total = p1 * p2
                if 1 <= total <= 400:
                    return total
            except ValueError:
                pass

    patterns = [
        r"(\d+)\s*(?:рулон(?:ов|а)?|рул(?:\.|\b))",
        r"(\d+)\s*(?:шт(?:\.|\b)|штук(?:и)?)",
        r"(\d+)\s*(?:пач(?:\.|\b)|пачек)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                val = int(m.group(1))
                if 1 <= val <= 200:
                    return val
            except ValueError:
                pass
    return 1


def parse_layer_count(text: str) -> int:
    """
    Extract layer count from product title/description.
    E.g. '3 слоя', '3-слойная', '4 слоя' -> 3 or 4
    """
    if not text:
        return 3
    m = re.search(r"(\d+)\s*(?:-?\s*сло[яйе][\w]*|сл(?:\.|\b))", text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return 3


class HHVacancyRecord(BaseModel):
    """Structured vacancy record extracted from HH.ru."""
    id: str
    title: str
    employer: str = ""
    salary: Optional[str] = None
    experience: Optional[str] = None
    snippet: Optional[str] = None
    url: str
    description: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    fit_markdown: Optional[str] = None
    decision: Optional[str] = None
    score: Optional[float] = None


class OzonProductRecord(BaseModel):
    """Structured product record extracted from Ozon."""
    id: str
    title: str
    vendor: Optional[str] = None
    price: float
    original_price: Optional[float] = None
    rating: float = 0.0
    reviews_count: int = 0
    rolls_count: int = 1
    layer_count: int = 3
    price_per_roll: float = 0.0
    url: str = ""
    is_forbidden_vendor: bool = False
    value_score: float = 0.0

    def compute_economics(self, forbidden_vendors: Optional[List[str]] = None) -> None:
        """Compute price per roll and check vendor restrictions."""
        if forbidden_vendors is None:
            forbidden_vendors = ["Yandex Fabrika", "Яндекс Фабрика", "Tuvio"]

        # Check vendor with punctuation normalization
        self.is_forbidden_vendor = False
        vendor_check = re.sub(r"[\W_]+", " ", f"{self.vendor or ''} {self.title}".lower())
        for fv in forbidden_vendors:
            norm_fv = re.sub(r"[\W_]+", " ", fv.lower())
            if norm_fv in vendor_check:
                self.is_forbidden_vendor = True
                break

        # Calculate unit price
        rolls = max(1, self.rolls_count)
        self.price_per_roll = round(self.price / rolls, 2)

        # Value score: favors lower price per roll, rewarded by rating & reviews
        import math
        confidence = math.log10(max(10, self.reviews_count + 10))
        quality_factor = (self.rating / 5.0) if self.rating > 0 else 0.7
        # Higher score = better deal
        self.value_score = round((quality_factor * confidence * 100.0) / (self.price_per_roll + 0.1), 3)


# CSS Selector extraction templates for Crawl4AI JsonCssExtractionStrategy
HH_SEARCH_SCHEMA = {
    "name": "HH Vacancies List",
    "baseSelector": "[data-qa='vacancy-serp__vacancy'], .vacancy-card--H_dp9GgL, [data-qa='serp-item__title']",
    "fields": [
        {"name": "title", "selector": "[data-qa='serp-item__title'], [data-qa='vacancy-serp__vacancy-title']", "type": "text"},
        {"name": "url", "selector": "[data-qa='serp-item__title'], a", "type": "attribute", "attribute": "href"},
        {"name": "employer", "selector": "[data-qa='vacancy-serp__vacancy-employer'], [data-qa='vacancy-serp__vacancy-company-name']", "type": "text"},
        {"name": "salary", "selector": "[data-qa='vacancy-serp__vacancy-compensation'], [data-serp-item__compensation]", "type": "text"},
        {"name": "experience", "selector": "[data-qa='vacancy-serp__vacancy-experience']", "type": "text"},
        {"name": "snippet", "selector": "[data-qa='vacancy-serp__vacancy_snippet_responsibility'], [data-qa='vacancy-serp__vacancy_snippet_requirement']", "type": "text"},
    ]
}

OZON_SEARCH_SCHEMA = {
    "name": "Ozon Product Cards",
    "baseSelector": "div.tile-root, div[data-widget='searchResultsV2'] > div, div.widget-search-result-container > div",
    "fields": [
        {"name": "title", "selector": "span.tsBody500Medium, span.tsBodyL, a span", "type": "text"},
        {"name": "url", "selector": "a.tile-hover-target, a[href*='/product/']", "type": "attribute", "attribute": "href"},
        {"name": "price", "selector": "span[class*='Price'], span.c3016-a1, span.tsHeadline500Medium", "type": "text"},
        {"name": "rating", "selector": "span[class*='Rating'], span[data-qa='rating']", "type": "text"},
        {"name": "reviews", "selector": "span[class*='Reviews'], span[data-qa='reviews']", "type": "text"},
        {"name": "vendor", "selector": "span[class*='Brand'], span.tsBodyControl400Small", "type": "text"},
    ]
}
