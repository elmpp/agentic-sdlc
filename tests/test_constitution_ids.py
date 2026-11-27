"""Article ids carry the product id, which inception allows to be 2-6 letters (inception._PID)."""

from valxel_sdlc.constitution import compose

PLATFORM = "---\nname: platform\nversion: 1.0.0\n---\n- **VX-1** Humans own intent. (Human)\n"


def test_a_five_letter_product_ids_articles_are_found():
    product = "---\nname: tnote\nversion: 0.1.0\n---\n- **TNOTE-1** Goals are measured. (Policy)\n"
    c = compose(PLATFORM, product, platform_sha="a" * 7, product_sha="b" * 7)
    assert c.product_articles() == ("TNOTE-1",)


def test_six_letters_is_the_limit():
    product = "---\nname: x\nversion: 0.1.0\n---\n- **ABCDEF-2** Six. (Policy)\n- **ABCDEFG-3** Seven. (Policy)\n"
    c = compose(PLATFORM, product, platform_sha="a" * 7, product_sha="b" * 7)
    assert "ABCDEF-2" in c.product_articles() and not any(a.startswith("ABCDEFG") for a in c.article_ids)
