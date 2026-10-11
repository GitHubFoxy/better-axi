from pathlib import Path
import pytest
from core.workflows.ozon_buyer import OzonBuyerWorkflow

FIXTURES_DIR = Path(__file__).parent / "fixtures"

@pytest.mark.asyncio
async def test_ozon_buyer_workflow_end_to_end():
    p1_html = (FIXTURES_DIR / "ozon_search_page_1.html").read_text(encoding="utf-8")
    p2_html = (FIXTURES_DIR / "ozon_search_page_2.html").read_text(encoding="utf-8")

    added_to_cart = []
    def mock_add_to_cart(url):
        added_to_cart.append(url)
        return {"status": "added", "target": url}

    workflow = OzonBuyerWorkflow(cart_action_fn=mock_add_to_cart)

    result = await workflow.run(
        query="Туалетная бумага 3 слоя",
        pages=2,
        confirm_add_to_cart=True,
        mock_pages_html={1: p1_html, 2: p2_html},
    )

    assert result["status"] == "success"
    assert result["total_extracted"] == 6
    # 2 forbidden products excluded (Yandex Fabrika & Tuvio)
    assert result["forbidden_or_rejected"] == 2
    assert result["eligible_count"] == 4

    # Winner should be Zewa Deluxe (35.0 ₽/roll, 4.9 rating)
    winner = result["winner"]
    assert winner is not None
    assert "Zewa Deluxe" in winner["title"]
    assert winner["rolls_count"] == 12
    assert winner["price_per_roll"] == 35.0
    assert winner["rating"] == 4.9

    # 2 alternatives present
    alts = result["alternatives"]
    assert len(alts) == 2

    # Cart action executed
    assert result["cart_action_executed"] is True
    assert len(added_to_cart) == 1
    assert "zewa-deluxe" in added_to_cart[0]
