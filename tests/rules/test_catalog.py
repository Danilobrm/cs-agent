import pytest

from cs_agent.rules.catalog import availability, description_conflicts, normalize_text


@pytest.mark.parametrize(
    ("name", "description"),
    [
        (
            "Music Man Bass 1X Electric Bass",
            "Contrabaixo elétrico Fender Jazz Bass com corpo em Alder",
        ),  # 135
        (
            "Yamaha Bass 3X Electric Bass",
            "Contrabaixo ativo de 5 cordas Ibanez com equalizador",
        ),  # 137
        (
            "Bateria Acústica Yamaha Kit 1 Studio",
            "Bateria acústica Pearl Export com cascos em Poplar",
        ),  # 139
        (
            "Bateria Acústica Pearl Kit 2 Studio",
            "Bateria acústica Tama com cascos 100% Birch",
        ),  # 140
        (
            "Teclado Sintetizador Korg Synth 1 Pro",
            "Sintetizador workstation Roland com 88 teclas",
        ),  # 142
        (
            "Teclado Sintetizador Roland Synth 3 Pro",
            "Teclado arranjador Yamaha com 61 teclas",
        ),  # 144
    ],
)
def test_conflicting_descriptions(name, description):
    assert description_conflicts(name, description)


@pytest.mark.parametrize(
    ("name", "description"),
    [
        (
            "Yamaha C40 Nylon Natural",
            "Violão clássico com tampo em Spruce. Ideal para estudantes.",
        ),  # 81
        (
            "Bateria Acústica Yamaha Kit 3 Studio",
            "Bateria acústica Yamaha Stage Custom com bumbos",
        ),  # 141
        (
            "Teclado Sintetizador Nord Synth 2 Pro",
            "Piano de palco Nord Stage com seções independentes",
        ),  # 143
        (
            "Fender Stratocaster American Pro II",
            "Guitarra elétrica Fender Stratocaster com 3 captadores",
        ),  # 145
    ],
)
def test_consistent_descriptions(name, description):
    assert not description_conflicts(name, description)


def test_brand_match_ignores_case_accents_and_needs_whole_words():
    assert description_conflicts("Violão Natural", "Corpo estilo FENDER clássico")
    assert not description_conflicts(
        "Violão Natural", "Som do Tamanho certo"
    )  # "Tama" inside a word
    assert not description_conflicts("MUSIC MAN Bass", "Baixo music man original")


def test_availability():
    assert availability("active", 3) == "available"
    assert availability("active", 0) == "out_of_stock"
    assert availability("discontinued", 5) == "discontinued"
    assert availability("coming_soon", 0) == "coming_soon"


def test_normalize_text():
    assert normalize_text("Três Lagoas ÃÕ") == "tres lagoas ao"
