from app.storage.dependencies import get_object_storage


def test_get_object_storage_uses_configured_bucket():
    get_object_storage.cache_clear()
    storage = get_object_storage()

    assert storage._bucket == "personalization"

    get_object_storage.cache_clear()
