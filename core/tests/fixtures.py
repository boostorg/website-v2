import pytest
from model_bakery import baker


@pytest.fixture
def rendered_content(db):
    return baker.make(
        "core.RenderedContent",
        cache_key="cache-key",
        content_original="Sample content",
        content_html="<p>Sample content</p>",
    )


@pytest.fixture
def mock_get_file_data(monkeypatch):
    def _mock_get_file_data(
        content,
        content_s3_key,
        content_s3_key_prefix="/archives/",
        content_type="text/html",
    ):
        def get_file_data(client, bucket_name, s3_key):
            if f"{content_s3_key_prefix}{content_s3_key}" == s3_key:
                result = {
                    "content": content,
                    "content_key": s3_key,
                    "content_type": content_type,
                    "last_modified": None,
                }
            else:
                result = None
            return result

        monkeypatch.setattr("core.boostrenderer.get_file_data", get_file_data)

    return _mock_get_file_data
