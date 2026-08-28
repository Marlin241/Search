import pytest

from app.job_search.remote_signals import is_remote_from_text


@pytest.mark.parametrize(
    "fragments,expected",
    [
        (("Poste 100% télétravail",), True),
        (("Paris", "Full remote position"), True),
        ((None, "Travail à distance / distanciel"), True),
        (("Dakar, Sénégal", "Présentiel obligatoire"), False),
        ((None, None), False),
        (("Mode hybride 3j/semaine",), True),
        (("Work From Home",), True),
    ],
)
def test_is_remote_from_text(fragments, expected):
    assert is_remote_from_text(*fragments) is expected
