from app.job_search.aggregator import search_jobs
from app.job_search.errors import JobSearchSourceError
from app.job_search.schemas import JobListing, SearchCriteria

_LISTING = JobListing(
    title="Développeur Python",
    company="Acme",
    location="Paris",
    snippet="...",
    url="https://example.com/1",
    source="fake",
    ats_type=None,
)


class WorkingClient:
    def search(self, criteria):
        return [_LISTING]


class FailingClient:
    def search(self, criteria):
        raise JobSearchSourceError("boom")


class _SingleUrlClient:
    def __init__(self, url: str):
        self._url = url

    def search(self, criteria):
        return [_LISTING.model_copy(update={"url": self._url})]


def test_search_jobs_merges_results_from_all_sources():
    listings, unavailable = search_jobs(
        SearchCriteria(keywords="python"),
        {
            "source_a": _SingleUrlClient("https://example.com/a"),
            "source_b": _SingleUrlClient("https://example.com/b"),
        },
    )
    assert len(listings) == 2
    assert unavailable == []


def test_search_jobs_sets_is_remote_from_text_heuristic():
    remote_listing = _listing(
        title="Dev", snippet="Poste en télétravail total", url="https://x/r"
    )

    class C:
        def search(self, criteria):
            return [remote_listing]

    listings, _ = search_jobs(SearchCriteria(keywords="dev"), {"c": C()})
    assert listings[0].is_remote is True


def test_search_jobs_remote_filter_keeps_only_is_remote_listings():
    on_site = _listing(title="Dev", snippet="Présentiel", url="https://x/1")
    remote = _listing(title="Dev", snippet="Full remote", url="https://x/2")

    class C:
        def search(self, criteria):
            return [on_site, remote]

    listings, _ = search_jobs(SearchCriteria(keywords="dev", remote=True), {"c": C()})
    assert [lst.url for lst in listings] == ["https://x/2"]


def test_search_jobs_dedupes_listings_sharing_a_url():
    shared = JobListing(
        title="Dev",
        company="Acme",
        location="Remote",
        snippet="...",
        url="https://example.com/same",
        source="a",
        ats_type=None,
    )

    class ClientA:
        def search(self, criteria):
            return [shared]

    class ClientB:
        def search(self, criteria):
            return [shared.model_copy(update={"source": "b"})]

    listings, _ = search_jobs(
        SearchCriteria(keywords="dev"),
        {"a": ClientA(), "b": ClientB()},
    )
    assert len(listings) == 1
    assert listings[0].source == "a"


def test_search_jobs_omits_failing_source_without_failing_the_whole_search():
    listings, unavailable = search_jobs(
        SearchCriteria(keywords="python"),
        {"source_a": WorkingClient(), "source_b": FailingClient()},
    )
    assert len(listings) == 1
    assert unavailable == ["source_b"]


def test_search_jobs_with_all_sources_failing_returns_empty_listings():
    listings, unavailable = search_jobs(
        SearchCriteria(keywords="python"),
        {"source_a": FailingClient(), "source_b": FailingClient()},
    )
    assert listings == []
    assert set(unavailable) == {"source_a", "source_b"}


def _listing(**overrides) -> JobListing:
    values = {
        "title": "Développeur Python",
        "company": "Acme",
        "location": "Paris",
        "snippet": "Poste sur site.",
        "url": "https://example.com/1",
        "source": "fake",
        "ats_type": None,
    }
    values.update(overrides)
    return JobListing(**values)


class StaticClient:
    """A source client returning a fixed list of listings, so the
    aggregator's post-filters can be exercised independently of any real
    source client."""

    def __init__(self, listings: list[JobListing]):
        self._listings = listings

    def search(self, criteria):
        return self._listings


def test_search_jobs_drops_listings_whose_title_matches_an_excluded_keyword():
    kept = _listing(title="Développeur Python", url="https://example.com/keep")
    dropped = _listing(
        title="Développeur Python - Alternance", url="https://example.com/drop"
    )

    listings, _ = search_jobs(
        SearchCriteria(keywords="python", exclude_keywords=["alternance"]),
        {"source_a": StaticClient([kept, dropped])},
    )

    assert [listing.url for listing in listings] == ["https://example.com/keep"]


def test_search_jobs_drops_listings_whose_snippet_matches_an_excluded_keyword():
    kept = _listing(url="https://example.com/keep")
    dropped = _listing(
        snippet="Contrat de STAGE de 6 mois.", url="https://example.com/drop"
    )

    listings, _ = search_jobs(
        # Lowercase criterion vs. uppercase snippet: the match is case-insensitive.
        SearchCriteria(keywords="python", exclude_keywords=["stage"]),
        {"source_a": StaticClient([kept, dropped])},
    )

    assert [listing.url for listing in listings] == ["https://example.com/keep"]


def test_search_jobs_without_exclude_keywords_keeps_everything():
    listings, _ = search_jobs(
        SearchCriteria(keywords="python"),
        {"source_a": StaticClient([_listing(title="Alternance développeur")])},
    )

    assert len(listings) == 1


def test_search_jobs_drops_non_alternance_listings_when_filtering_for_alternance():
    # Regression test: France Travail has no typeContrat code for
    # "alternance" (see france_travail.py), so a plain CDI/CDD offer it
    # returns unfiltered must still be dropped here rather than leak through
    # as if it were an apprenticeship.
    kept = _listing(
        title="Développeur Python en alternance", url="https://example.com/keep"
    )
    dropped = _listing(
        title="Développeur Python (H/F)",
        snippet="Poste en CDI, statut cadre.",
        url="https://example.com/drop",
    )

    listings, _ = search_jobs(
        SearchCriteria(keywords="python", contract_type="alternance"),
        {"source_a": StaticClient([kept, dropped])},
    )

    assert [listing.url for listing in listings] == ["https://example.com/keep"]


def test_search_jobs_does_not_text_filter_natively_supported_contract_types():
    # "cdi" is filtered server-side by France Travail already; the
    # aggregator must not additionally require the word "CDI" to appear in
    # the snippet, since a short excerpt often won't mention it at all.
    listing = _listing(snippet="Poste sur site, aucune mention du type de contrat.")

    listings, _ = search_jobs(
        SearchCriteria(keywords="python", contract_type="cdi"),
        {"source_a": StaticClient([listing])},
    )

    assert len(listings) == 1


def test_search_jobs_with_remote_true_keeps_only_listings_with_a_remote_indicator():
    on_site = _listing(
        location="Paris", snippet="Poste sur site.", url="https://example.com/on-site"
    )
    remote_location = _listing(
        location="Remote", snippet="Poste ouvert.", url="https://example.com/remote"
    )
    remote_snippet = _listing(
        location="Lyon",
        snippet="Télétravail intégral possible.",
        url="https://example.com/teletravail",
    )
    distanciel_snippet = _listing(
        location="Nantes",
        snippet="Travail en DISTANCIEL.",
        url="https://example.com/distanciel",
    )

    listings, _ = search_jobs(
        SearchCriteria(keywords="python", remote=True),
        {
            "source_a": StaticClient(
                [on_site, remote_location, remote_snippet, distanciel_snippet]
            )
        },
    )

    assert [listing.url for listing in listings] == [
        "https://example.com/remote",
        "https://example.com/teletravail",
        "https://example.com/distanciel",
    ]


def test_search_jobs_with_remote_not_requested_keeps_on_site_listings():
    on_site = _listing(location="Paris", snippet="Poste sur site.")

    for criteria in (
        SearchCriteria(keywords="python"),
        SearchCriteria(keywords="python", remote=False),
    ):
        listings, _ = search_jobs(criteria, {"source_a": StaticClient([on_site])})
        assert len(listings) == 1


def test_search_jobs_remote_filter_tolerates_missing_location():
    without_location = _listing(
        location=None, snippet="Full remote.", url="https://example.com/keep"
    )
    dropped = _listing(
        location=None, snippet="Sur site.", url="https://example.com/drop"
    )

    listings, _ = search_jobs(
        SearchCriteria(keywords="python", remote=True),
        {"source_a": StaticClient([without_location, dropped])},
    )

    assert [listing.url for listing in listings] == ["https://example.com/keep"]


def test_search_jobs_applies_filters_after_merging_all_sources():
    listings, unavailable = search_jobs(
        SearchCriteria(keywords="python", remote=True, exclude_keywords=["alternance"]),
        {
            "source_a": StaticClient(
                [_listing(location="Remote", url="https://example.com/a")]
            ),
            "source_b": StaticClient(
                [
                    _listing(
                        title="Alternance dev",
                        location="Remote",
                        url="https://example.com/b",
                    ),
                    _listing(location="Paris", url="https://example.com/c"),
                ]
            ),
            "source_c": FailingClient(),
        },
    )

    assert [listing.url for listing in listings] == ["https://example.com/a"]
    assert unavailable == ["source_c"]
