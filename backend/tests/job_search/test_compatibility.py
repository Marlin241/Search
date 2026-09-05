from datetime import UTC, datetime, timedelta

from app.job_search.compatibility import score_breakdown, score_listing
from app.job_search.schemas import JobListing
from app.models.candidate_profile import CandidateProfile


def _listing(**overrides) -> JobListing:
    defaults = {
        "title": "Développeur Python",
        "company": "Acme",
        "location": "Paris",
        "snippet": "Poste de développeur, 3 ans d'expérience requis.",
        "url": "https://example.com/job/1",
        "source": "adzuna",
        "ats_type": None,
    }
    defaults.update(overrides)
    return JobListing(**defaults)


def _profile(**overrides) -> CandidateProfile:
    defaults = {
        "user_id": 1,
        "desired_job_titles": ["Développeur Python"],
        "seniority_level": "confirme_plus",
        "desired_locations": ["Paris"],
        "remote_preference": False,
        "salary_min": None,
        "salary_max": None,
    }
    defaults.update(overrides)
    return CandidateProfile(**defaults)


def test_no_profile_returns_neutral_score():
    assert score_listing(_listing(), None) == 50


def test_matching_title_location_seniority_scores_high():
    score = score_listing(_listing(), _profile())
    assert score >= 85


def test_unrelated_title_scores_lower_than_matching_title():
    matching = score_listing(_listing(), _profile())
    unrelated = score_listing(_listing(title="Comptable senior"), _profile())
    assert unrelated < matching


def test_missing_location_is_not_evaluated():
    listing = _listing(location=None)
    score = score_breakdown(listing, _profile())
    assert score["location"] is None


def test_remote_preference_matches_remote_listing():
    # is_remote is authoritative now (set by the aggregator / remote-only
    # sources); _score_location no longer re-derives it from the text.
    listing = _listing(
        location="Télétravail", snippet="Poste 100% télétravail.", is_remote=True
    )
    profile = _profile(desired_locations=[], remote_preference=True)
    score = score_breakdown(listing, profile)
    assert score["location"] == 100


def test_no_location_constraint_is_not_evaluated():
    listing = _listing(location="Lyon")
    profile = _profile(desired_locations=[], remote_preference=False)
    score = score_breakdown(listing, profile)
    assert score["location"] is None


def test_seniority_within_range_scores_full():
    listing = _listing(snippet="Poste ouvert, 4 ans d'expérience.")
    profile = _profile(seniority_level="confirme_plus")
    score = score_breakdown(listing, profile)
    assert score["seniority"] == 100


def test_seniority_far_outside_range_scores_low():
    listing = _listing(snippet="Poste junior, 0 ans d'expérience.")
    profile = _profile(seniority_level="senior")
    score = score_breakdown(listing, profile)
    assert score["seniority"] < 50


def test_seniority_no_mention_in_snippet_is_not_evaluated():
    listing = _listing(snippet="Rejoignez une équipe dynamique.")
    profile = _profile(seniority_level="senior")
    score = score_breakdown(listing, profile)
    assert score["seniority"] is None


# Salary tests below rely on the currency defaulting to XOF on both sides
# when unset (see _score_salary) - the default `_listing()` source is
# "adzuna" but none of these listings set salary_currency, so they compare
# as XOF vs XOF just like a Senegalese-source listing would.


def test_salary_within_range_scores_full():
    listing = _listing(salary="40 000 - 45 000 FCFA / mois", source="senjob")
    profile = _profile(salary_min=35000, salary_max=50000)
    score = score_breakdown(listing, profile)
    assert score["salary"] == 100


def test_salary_above_range_is_not_penalized():
    listing = _listing(salary="60 000 - 65 000 FCFA / mois", source="senjob")
    profile = _profile(salary_min=35000, salary_max=50000)
    score = score_breakdown(listing, profile)
    assert score["salary"] == 90


def test_salary_below_range_is_penalized():
    listing = _listing(salary="20 000 FCFA / mois", source="senjob")
    profile = _profile(salary_min=35000, salary_max=50000)
    score = score_breakdown(listing, profile)
    assert score["salary"] is not None and score["salary"] < 90


def test_no_salary_expectation_is_not_evaluated():
    listing = _listing(salary="40 000 FCFA / mois", source="senjob")
    profile = _profile(salary_min=None, salary_max=None)
    score = score_breakdown(listing, profile)
    assert score["salary"] is None


def test_no_salary_on_listing_is_not_evaluated():
    listing = _listing(salary=None, source="senjob")
    profile = _profile(salary_min=35000, salary_max=50000)
    score = score_breakdown(listing, profile)
    assert score["salary"] is None


def test_salary_not_evaluated_when_currencies_differ():
    # France Travail/Adzuna quote real salaries, but in euros - comparing
    # the raw numbers against an XOF expectation would compare the wrong
    # currency, so the criterion is left unevaluated.
    listing = _listing(salary="40 000 - 45 000 EUR / an", salary_currency="EUR")
    profile = _profile(salary_min=35000, salary_max=50000)  # implicit XOF
    score = score_breakdown(listing, profile)
    assert score["salary"] is None


def test_salary_evaluated_when_currencies_match_non_xof():
    listing = _listing(salary="40 000 - 45 000 EUR / an", salary_currency="EUR")
    profile = _profile(salary_min=35000, salary_max=50000, salary_currency="EUR")
    score = score_breakdown(listing, profile)
    assert score["salary"] == 100


def test_recent_listing_scores_full_freshness():
    listing = _listing(posted_at=datetime.now(UTC) - timedelta(days=1))
    score = score_breakdown(listing, _profile())
    assert score["freshness"] == 100


def test_old_listing_scores_low_freshness():
    listing = _listing(posted_at=datetime.now(UTC) - timedelta(days=120))
    score = score_breakdown(listing, _profile())
    assert score["freshness"] == 15


def test_missing_posted_at_is_not_evaluated():
    listing = _listing(posted_at=None)
    score = score_breakdown(listing, _profile())
    assert score["freshness"] is None


def test_nothing_evaluable_falls_back_to_neutral_overall():
    # No desired job titles/locations/seniority/salary, listing has no
    # location/salary/posted_at either - literally nothing to compare.
    listing = _listing(
        location=None,
        salary=None,
        posted_at=None,
        source="senjob",
        snippet="Poste disponible.",
    )
    profile = _profile(
        desired_job_titles=[],
        seniority_level=None,
        desired_locations=[],
        salary_min=None,
        salary_max=None,
    )
    score = score_breakdown(listing, profile)
    assert all(
        score[key] is None
        for key in ("title", "location", "seniority", "salary", "freshness")
    )
    assert score["overall"] == 50


def test_score_breakdown_overall_matches_score_listing():
    listing = _listing()
    profile = _profile()
    assert score_breakdown(listing, profile)["overall"] == score_listing(
        listing, profile
    )
