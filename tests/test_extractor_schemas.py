import pytest
from core.extractor.schemas import (
    parse_price,
    parse_rating,
    parse_reviews_count,
    parse_rolls_count,
    parse_layer_count,
    HHVacancyRecord,
    OzonProductRecord,
)

def test_parse_price():
    assert parse_price("420 ₽") == 420.0
    assert parse_price("1 299 ₽") == 1299.0
    assert parse_price("99.50") == 99.50
    assert parse_price("99,99 руб") == 99.99
    assert parse_price(None) == 0.0
    assert parse_price("") == 0.0

def test_parse_rolls_count():
    assert parse_rolls_count("Туалетная бумага Zewa 12 рулонов") == 12
    assert parse_rolls_count("Papia 3 слоя, 8 шт") == 8
    assert parse_rolls_count("Soffione 4 рул") == 4
    assert parse_rolls_count("Без указания количества") == 1

def test_parse_layer_count():
    assert parse_layer_count("Туалетная бумага 3 слоя") == 3
    assert parse_layer_count("Zewa 4-слойная 8 рулонов") == 4
    assert parse_layer_count("2 сл.") == 2
    assert parse_layer_count("Обычная") == 3

def test_parse_rating_and_reviews():
    assert parse_rating("4.9 ★") == 4.9
    assert parse_rating("4,85") == 4.85
    assert parse_rating(None) == 0.0

    assert parse_reviews_count("3 120 отзывов") == 3120
    assert parse_reviews_count("15") == 15
    assert parse_reviews_count(None) == 0

def test_ozon_unit_economics_and_forbidden_vendors():
    # Regular product
    p1 = OzonProductRecord(
        id="1",
        title="Туалетная бумага Zewa 3 слоя 12 рулонов",
        vendor="Zewa",
        price=420.0,
        rating=4.9,
        reviews_count=3000,
        rolls_count=12,
        layer_count=3,
    )
    p1.compute_economics()
    assert p1.is_forbidden_vendor is False
    assert p1.price_per_roll == 35.0
    assert p1.value_score > 0

    # Forbidden product: Yandex Fabrika
    p2 = OzonProductRecord(
        id="2",
        title="Туалетная бумага Yandex Fabrika 3 слоя 16 рулонов",
        vendor="Yandex Fabrika",
        price=380.0,
        rating=4.8,
        reviews_count=1000,
        rolls_count=16,
        layer_count=3,
    )
    p2.compute_economics()
    assert p2.is_forbidden_vendor is True

    # Forbidden product: Tuvio
    p3 = OzonProductRecord(
        id="3",
        title="Туалетная бумага Tuvio 3 слоя 8 рулонов",
        vendor="Tuvio",
        price=290.0,
        rating=4.7,
        reviews_count=500,
        rolls_count=8,
        layer_count=3,
    )
    p3.compute_economics()
    assert p3.is_forbidden_vendor is True

def test_parse_multipacks_and_wet_wipes():
    # Multipacks
    assert parse_rolls_count('Туалетная бумага 8 рулонов х 2 шт') == 16
    assert parse_rolls_count('2 пачки по 8 рулонов') == 16
    assert parse_rolls_count('4 пачки по 4 рул') == 16
    # Wet wipes: should default to 1 roll so unit price is not artificially crushed
    assert parse_rolls_count('Влажная туалетная бумага 120 шт') == 1
