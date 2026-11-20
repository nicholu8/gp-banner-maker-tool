import pytest

from growbanner.export import slugify
from growbanner.schemes import match_scheme


@pytest.mark.parametrize("loc,banner", [
    ("Braddock", "#8DC63F"), ("braddock farm", "#8DC63F"), ("BRADDOCK", "#8DC63F"),
    ("Shiloh", "#FFC20E"), ("Shiloh Street Farm", "#FFC20E"),
    ("Garden Dreams", "#F7941D"), ("garden  dreams!", "#F7941D"),
    ("GRC", "#003510"), ("Garden Resource Center", "#003510"),
    ("Virtual", "#981B1E"), ("Community Forge", "#981B1E"), ("GP Office", "#981B1E"),
    ("", "#981B1E"), ("Somewhere new", "#981B1E"), ("Bigrcity", "#981B1E"),
])
def test_match(loc, banner):
    assert match_scheme(loc).banner == banner


def test_text_colors():
    assert match_scheme("Braddock").text == "#000000"
    assert match_scheme("GRC").text == "#FFFFFF"
    assert match_scheme("Virtual").text == "#FFFFFF"


@pytest.mark.parametrize("title,slug", [
    ("Spring Seedling Sale", "spring-seedling-sale"),
    ("Q&A: Café Night — it's free!", "q-a-cafe-night-it-s-free"),
    ("!!!", "banner"), ("", "banner"),
])
def test_slugify(title, slug):
    assert slugify(title) == slug
