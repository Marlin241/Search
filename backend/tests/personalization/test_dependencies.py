from app.personalization.dependencies import get_cover_letter_generator, get_cv_rewriter


def test_cv_rewriter_client_has_bounded_timeout_and_no_sdk_retries():
    get_cv_rewriter.cache_clear()
    rewriter = get_cv_rewriter()
    client = rewriter._client

    assert client.timeout == 60.0
    assert client.max_retries == 0

    get_cv_rewriter.cache_clear()


def test_cover_letter_generator_client_has_bounded_timeout_and_no_sdk_retries():
    get_cover_letter_generator.cache_clear()
    generator = get_cover_letter_generator()
    client = generator._client

    assert client.timeout == 60.0
    assert client.max_retries == 0

    get_cover_letter_generator.cache_clear()
