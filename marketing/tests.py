import logging
from unittest.mock import patch

import pytest


def test_whitepaper_view(tp):
    tp.assertGoodView("whitepaper", slug="_example")


@pytest.mark.parametrize("url_stem", ["qrc", "bsm"])
def test_plausible_redirect_and_plausible_payload(tp, url_stem):
    """XFF present; querystring preserved; payload/headers correct."""
    with patch("marketing.views.requests.post", return_value=None) as post_mock:
        url = f"/{url_stem}/pv-01/library/latest/beast/?x=1&y=2"
        res = tp.get(url)

    tp.response_302(res)
    assert res["Location"] == "/library/latest/beast/?x=1&y=2"

    # Plausible call
    (endpoint,), kwargs = post_mock.call_args
    assert endpoint == "https://plausible.io/api/event"

    # View uses request.path, so no querystring in payload URL
    assert kwargs["json"] == {
        "name": "pageview",
        "domain": "qrc.boost.org",
        "url": f"http://testserver/{url_stem}/pv-01/library/latest/beast/",
        "referrer": "",  # matches view behavior with no forwarded referer
    }

    headers = kwargs["headers"]
    assert headers["Content-Type"] == "application/json"
    assert kwargs["timeout"] == 2.0


def test_qrc_falls_back_to_remote_addr_when_no_xff(tp):
    """No XFF provided -> uses REMOTE_ADDR (127.0.0.1 in Django test client)."""
    with patch("marketing.views.requests.post", return_value=None) as post_mock:
        res = tp.get("/qrc/camp/library/latest/algorithm/")

    tp.response_302(res)
    assert res["Location"] == "/library/latest/algorithm/"

    (_, kwargs) = post_mock.call_args
    headers = kwargs["headers"]
    assert headers["X-Forwarded-For"] == "127.0.0.1"  # Django test client default


def test_qrc_logs_plausible_error_but_still_redirects(tp, caplog):
    """Plausible post raises -> error logged; redirect not interrupted."""
    with patch("marketing.views.requests.post", side_effect=RuntimeError("boom")):
        with caplog.at_level(logging.ERROR, logger="core.views"):
            res = tp.get("/qrc/c1/library/", HTTP_USER_AGENT="ua")

    tp.response_302(res)
    assert res["Location"] == "/library/"
    assert any("Plausible event post failed" in r.message for r in caplog.records)
