from app.ats_adapters.dependencies import get_custom_field_answerer


def test_custom_field_answerer_client_has_bounded_timeout_and_no_sdk_retries():
    get_custom_field_answerer.cache_clear()
    answerer = get_custom_field_answerer()
    client = answerer._client

    assert client.timeout == 30.0
    assert client.max_retries == 0

    get_custom_field_answerer.cache_clear()
