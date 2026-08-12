from app.job_search.keyword_matching import keyword_matches_title


def test_empty_keyword_matches_everything():
    assert keyword_matches_title("", "Anything") is True


def test_direct_substring_match_is_case_insensitive():
    assert keyword_matches_title("python", "Backend Python Engineer") is True


def test_direct_match_ignores_accents_on_both_sides():
    assert keyword_matches_title("developpeur", "Développeur Python") is True
    assert keyword_matches_title("développeur", "Developpeur Python") is True


def test_no_match_when_keyword_absent_and_no_synonym():
    assert keyword_matches_title("comptable", "Software Engineer") is False


def test_french_keyword_matches_english_synonym_title():
    assert keyword_matches_title("développeur", "Software Engineer") is True
    assert keyword_matches_title("développeur", "Senior Developer") is True
    assert keyword_matches_title("ingénieur", "Endpoint Engineer") is True
    assert keyword_matches_title("comptable", "Accountant") is True
    assert keyword_matches_title("ressources humaines", "HR Systems Analyst") is True


def test_english_keyword_still_matches_directly_without_needing_a_synonym():
    assert keyword_matches_title("engineer", "Endpoint Engineer") is True
