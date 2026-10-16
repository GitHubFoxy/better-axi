from pathlib import Path
import pytest
from core.extractor.bridge import Crawl4AIBridge, select_page_target
from core.extractor.markdown import generate_fit_markdown

FIXTURES_DIR = Path(__file__).parent / "fixtures"

def test_select_page_target_requires_unique_or_exact_url():
    pages = [
        {"id": "old", "url": "https://hh.ru/search/vacancy?text=old"},
        {"id": "current", "url": "https://hh.ru/search/vacancy?text=current"},
    ]

    with pytest.raises(RuntimeError, match="Pass its exact URL"):
        select_page_target(pages)
    assert select_page_target(pages, pages[1]["url"]) == pages[1]
    with pytest.raises(RuntimeError, match="found 0"):
        select_page_target(pages, "https://hh.ru/search/vacancy?text=missing")

def test_parse_hh_search_html_ignores_unscoped_vacancy_links():
    bridge = Crawl4AIBridge()
    html = "<html><body><a href='/vacancy/123'>Recommendation</a></body></html>"
    assert bridge.parse_hh_search_html(html) == []

def test_parse_hh_search_html():
    html = (FIXTURES_DIR / "hh_search_page.html").read_text(encoding="utf-8")
    bridge = Crawl4AIBridge()
    vacancies = bridge.parse_hh_search_html(html)

    assert len(vacancies) == 3
    v1 = vacancies[0]
    assert v1.id == "10101001"
    assert "FastAPI" in v1.title
    assert v1.employer == "TechCorp Solutions"
    assert "180 000" in (v1.salary or "")
    assert "1–3 года" in (v1.experience or "")
    assert "FastAPI" in (v1.snippet or "")

    v2 = vacancies[1]
    assert v2.id == "10101002"
    assert "1С" in v2.title

def test_parse_hh_vacancy_detail_html():
    search_html = (FIXTURES_DIR / "hh_search_page.html").read_text(encoding="utf-8")
    detail_html = (FIXTURES_DIR / "hh_vacancy_page.html").read_text(encoding="utf-8")
    bridge = Crawl4AIBridge()

    base_vac = bridge.parse_hh_search_html(search_html)[0]
    detailed = bridge.parse_hh_vacancy_detail_html(detail_html, base_record=base_vac)

    assert detailed.id == "10101001"
    assert "FastAPI" in detailed.title
    assert "Docker" in detailed.skills
    assert "PostgreSQL" in detailed.skills
    assert "начните сопроводительное письмо со слов LOL" in (detailed.description or "")
    assert detailed.fit_markdown is not None

def test_generate_fit_markdown():
    html = """
    <html>
      <body>
        <script>console.log('noise');</script>
        <h1>Backend Developer</h1>
        <p>Requirements:</p>
        <ul>
          <li>Python 3.11</li>
          <li>PostgreSQL</li>
        </ul>
        <footer>© 2026 Все права защищены. Cookie notice</footer>
      </body>
    </html>
    """
    md = generate_fit_markdown(html)
    assert "# Backend Developer" in md
    assert "- Python 3.11" in md
    assert "- PostgreSQL" in md
    assert "noise" not in md
    assert "Cookie notice" not in md

def test_parse_ozon_search_html():
    html_p1 = (FIXTURES_DIR / "ozon_search_page_1.html").read_text(encoding="utf-8")
    bridge = Crawl4AIBridge()
    products = bridge.parse_ozon_search_html(html_p1, page_num=1)

    assert len(products) == 3
    # Zewa
    zewa = next(p for p in products if "Zewa" in p.title)
    assert zewa.price == 420.0
    assert zewa.rolls_count == 12
    assert zewa.layer_count == 3
    assert zewa.rating == 4.9
    assert zewa.price_per_roll == 35.0
    assert zewa.is_forbidden_vendor is False

    # Yandex Fabrika
    yf = next(p for p in products if "Yandex Fabrika" in p.title)
    assert yf.is_forbidden_vendor is True
