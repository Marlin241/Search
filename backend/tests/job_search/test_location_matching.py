import pytest

from app.job_search.location_matching import location_matches


@pytest.mark.parametrize(
    ("needle", "offer_location", "expected"),
    [
        # no needle -> everything matches
        ("", "Dakar", True),
        (None, None, True),
        # offer without a location is not filtered out
        ("Dakar", "", True),
        ("Dakar", None, True),
        # plain (accent-insensitive) substring, either direction
        ("Dakar", "Dakar, Sénégal", True),
        ("senegal", "Dakar, Sénégal", True),
        ("Abidjan", "Cocody, Abidjan", True),
        # the reported bug: a Dakar neighbourhood / landmark
        ("Dakar", "LIBERTE 6, en face UNO", True),
        ("Dakar", "Diamniadio, Sénégal", True),
        ("Dakar", "Parcelles Assainies", True),
        # Abidjan neighbourhoods
        ("Abidjan", "Treichville", True),
        ("Abidjan", "Yopougon Zone Industrielle", True),
        # country-only offer matches a city search from that country
        ("Dakar", "Sénégal", True),
        ("Abidjan", "Côte d'Ivoire", True),
        # ... but not a city search from another country
        ("Dakar", "Côte d'Ivoire", False),
        ("Abidjan", "Sénégal", False),
        # a different city in the same country is NOT a match
        ("Dakar", "Thiès, Sénégal", False),
        ("Dakar", "Saint-Louis", False),
        ("Abidjan", "Bouaké", False),
    ],
)
def test_location_matches(needle, offer_location, expected):
    assert location_matches(needle, offer_location) is expected
