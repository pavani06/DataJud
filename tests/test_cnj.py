import pytest

from app.cnj import infer_tribunal, normalize_cnj


def synthetic_number(segment, court, origin="0000"):
    """Synthetic test identifier; never interpreted as a real court record."""
    stem = f"00012342024{segment}{court:02d}{origin}"
    check = 98 - int(stem + "00") % 97
    return stem[:7] + f"{check:02d}" + stem[7:]


@pytest.mark.parametrize("number", ["00409435319968260114", "0040943-53.1996.8.26.0114"])
def test_published_tjsp_example_preserves_leading_zeroes(number):
    # Example from https://www.tjsp.jus.br/download/geraisintranet/novidades_distribuidor_civel_producao_cnj65.pdf
    assert normalize_cnj(number) == "00409435319968260114"
    assert infer_tribunal(number) == "TJSP"


@pytest.mark.parametrize("number", [
    "", "123", "0040943-53.1996.8.26.0114 ", "0040943/53.1996.8.26.0114",
    "0040943-54.1996.8.26.0114", "00409435319968260115", "٠" * 20,
    "１" * 20, None, 409435319968260114, "00000000000000000000",
])
def test_invalid_numbers_fail_explicitly(number):
    with pytest.raises(ValueError, match="CNJ"):
        normalize_cnj(number)
    with pytest.raises(ValueError):
        infer_tribunal(number)


@pytest.mark.parametrize("segment,court,expected", [
    (3, 0, "STJ"), (5, 0, "TST"), (6, 0, "TSE"), (7, 0, "STM"),
    (4, 1, "TRF1"), (4, 6, "TRF6"), (5, 1, "TRT1"), (5, 24, "TRT24"),
    (8, 3, "TJAP"), (8, 4, "TJAM"), (8, 7, "TJDFT"),
    (8, 11, "TJMT"), (8, 12, "TJMS"), (8, 25, "TJSE"), (8, 26, "TJSP"),
    (6, 7, "TRE-DF"), (6, 25, "TRE-SE"), (6, 26, "TRE-SP"),
    (9, 13, "TJMMG"), (9, 21, "TJMRS"), (9, 26, "TJMSP"),
])
def test_origin_inference_follows_cnj_segments_and_annexes(segment, court, expected):
    assert infer_tribunal(synthetic_number(segment, court)) == expected


@pytest.mark.parametrize("segment,court", [
    (1, 0), (2, 0), (3, 1), (4, 0), (4, 7), (4, 90), (5, 25), (5, 90),
    (6, 28), (7, 1), (7, 12), (8, 0), (8, 28), (9, 1), (0, 26),
])
def test_unknown_or_unmapped_origins_require_an_explicit_court(segment, court):
    with pytest.raises(ValueError, match="tribunal explicitamente"):
        infer_tribunal(synthetic_number(segment, court))


def test_superior_origin_requires_origin_unit_zero():
    with pytest.raises(ValueError, match="tribunal explicitamente"):
        infer_tribunal(synthetic_number(3, 0, "0001"))


def test_checksum_rejects_noncanonical_00_and_99_even_if_mod97_matches():
    # Canonical digits are 02..98. Pure remainder validation would also accept
    # a noncanonical pair differing by 97; the generation formula rejects it.
    for check in ("00", "99"):
        for sequential in range(1, 200):
            stem = f"{sequential:07d}20248260001"
            number = stem[:7] + check + stem[7:]
            if int(stem + check) % 97 == 1:
                with pytest.raises(ValueError, match="verificador"):
                    normalize_cnj(number)
                break
        else:
            pytest.fail("Could not construct noncanonical checksum regression fixture")
