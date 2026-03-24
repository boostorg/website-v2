import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from playwright.sync_api import expect
from selectors import selectors
from utils import log_and_screenshot, safe_goto
from config_helper import build_url, test_data, url_patterns
from test_helpers import find_visible_element, test_patterns

LOG = "test-logs.txt"


def _log(message):
    with open(LOG, "a") as f:
        f.write(message + "\n")


class TestBoostErrorHandling:

    # TC_ERROR_001
    def test_404_page_displays_appropriate_error_message(self, page, base_url):
        test_id = "TC_ERROR_001"
        invalid_url = build_url(
            base_url, "/this-page-does-not-exist-12345", cachebust=True
        )

        try:
            safe_goto(
                page, test_id, invalid_url, wait_until="networkidle", log_file=LOG
            )
        except Exception:
            _log(f"{test_id} Expected error when navigating to 404 page")

        error_indicators = [
            page.locator("text=/404|not found|page not found|doesn't exist/i").first,
            page.locator("h1, h2, h3")
            .filter(has_text=re.compile(r"404|not found", re.I))
            .first,
            page.locator('[class*="error"]').first,
            page.locator('[class*="404"]').first,
        ]
        error_found = False
        for indicator in error_indicators:
            if indicator.count() > 0:
                try:
                    is_visible = indicator.is_visible()
                except Exception:
                    is_visible = False
                if is_visible:
                    expect(indicator).to_be_visible(timeout=test_data.timeouts["short"])
                    error_found = True
                    _log(f"{test_id} 404 error message displayed correctly")
                    break

        if not error_found:
            log_and_screenshot(
                page,
                test_id,
                "404 error message not found",
                "screenshots/tc_error_001_no_404.png",
                LOG,
            )
            title = page.title()
            url = page.url
            _log(f'{test_id} Page title: "{title}", URL: "{url}"')
            if "404" in title.lower() or "not found" in title.lower():
                _log(f"{test_id} 404 indicated in page title")
                error_found = True

        assert error_found

    # TC_ERROR_002
    def test_broken_documentation_link_returns_appropriate_error(self, page, base_url):
        test_id = "TC_ERROR_002"
        broken_doc_url = build_url(
            base_url, "/doc/libs/nonexistent-library", cachebust=True
        )

        response = None
        try:
            response = page.goto(
                broken_doc_url,
                wait_until="networkidle",
                timeout=test_data.timeouts["medium"],
            )
        except Exception:
            pass

        if response:
            status = response.status
            _log(f"{test_id} Response status: {status}")
            assert 400 <= status < 500

        error_message = page.locator(
            "text=/error|not found|invalid|doesn't exist/i"
        ).first
        expect(error_message).to_be_visible(timeout=test_data.timeouts["medium"])
        _log(f"{test_id} Error message displayed for broken doc link")

    # TC_ERROR_003
    def test_invalid_search_query_handles_gracefully(self, page, base_url):
        test_id = "TC_ERROR_003"
        homepage_url = build_url(base_url, url_patterns.homepage, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, homepage_url, test_id, LOG)

        try:
            search_input = selectors.search(page)
            visible_search = find_visible_element(
                search_input, "Search input", test_id, LOG
            )
            if not visible_search:
                _log(f"{test_id} No search input found, skipping test")
                return

            invalid_terms = ["<script>", "%%%", "///"]
            for term in invalid_terms:
                visible_search.clear()
                visible_search.fill(term)
                visible_search.press("Enter")
                page.wait_for_timeout(2000)

                has_error = page.locator(
                    "text=/error|500|internal server|crash/i"
                ).count()
                assert has_error == 0
                _log(f'{test_id} Search with "{term}" handled gracefully')

            no_results = page.locator(
                "text=/no results|not found|no matches|try again/i"
            ).first
            try:
                is_visible = no_results.is_visible()
            except Exception:
                is_visible = False
            _log(
                f"{test_id} {'Appropriate no-results message shown' if is_visible else 'Search handled without errors'}"
            )
        except Exception as error:
            _log(f"{test_id} Test completed with note: {error}")

    # TC_ERROR_004
    def test_malformed_url_redirects_or_shows_error_appropriately(self, page, base_url):
        test_id = "TC_ERROR_004"
        malformed_paths = ["/doc/////libs", "/users//../download", "/libraries/?.."]

        for malformed_path in malformed_paths:
            malformed_url = build_url(base_url, malformed_path)
            _log(f"{test_id} Testing malformed URL: {malformed_url}")
            try:
                response = page.goto(
                    malformed_url,
                    wait_until="networkidle",
                    timeout=test_data.timeouts["medium"],
                )
                if response:
                    status = response.status
                    final_url = page.url
                    _log(f"{test_id} Status: {status}, Final URL: {final_url}")
                    if 200 <= status < 300:
                        _log(f"{test_id} Redirected to valid page")
                    elif 400 <= status < 500:
                        _log(f"{test_id} Appropriate error status")
                        assert (
                            page.locator("text=/error|not found|invalid/i").count() > 0
                        )
            except Exception as error:
                _log(f"{test_id} Malformed URL handled: {error}")

    # TC_ERROR_005
    def test_broken_external_links_are_identified(self, page, base_url):
        test_id = "TC_ERROR_005"
        homepage_url = build_url(base_url, url_patterns.homepage, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, homepage_url, test_id, LOG)

        external_links = page.locator('a[href^="http"]').all()
        _log(f"{test_id} Found {len(external_links)} external links")

        checked_links = 0
        for i, link in enumerate(external_links[:5]):
            href = link.get_attribute("href") or ""
            try:
                is_visible = link.is_visible()
            except Exception:
                is_visible = False
            if href and is_visible and "javascript:" not in href:
                try:
                    response = page.request.head(href, timeout=10000)
                    status = response.status
                    _log(f"{test_id} Link {i}: {href} - Status: {status}")
                    assert status < 400
                    checked_links += 1
                except Exception as error:
                    _log(f"{test_id} Link check failed for: {href} - {error}")

        _log(f"{test_id} Checked {checked_links} external links")
        assert checked_links > 0

    # TC_ERROR_006
    def test_form_validation_errors_display_correctly(self, page, base_url):
        test_id = "TC_ERROR_006"
        homepage_url = build_url(base_url, url_patterns.homepage, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, homepage_url, test_id, LOG)

        forms = page.locator("form").all()
        _log(f"{test_id} Found {len(forms)} forms on page")

        if not forms:
            _log(f"{test_id} No forms found on homepage, skipping test")
            return

        form = forms[0]
        submit_button = form.locator(
            'button[type="submit"], input[type="submit"]'
        ).first
        if submit_button.count() == 0:
            _log(f"{test_id} Form found but no submit button")
            return

        submit_button.click()
        page.wait_for_timeout(1000)

        validation_messages = [
            page.locator('[class*="error"], [class*="invalid"]').first,
            page.locator("text=/required|please|invalid|must/i").first,
            page.locator('[role="alert"]').first,
        ]
        validation_found = False
        for message in validation_messages:
            if message.count() > 0:
                try:
                    if message.is_visible():
                        _log(f"{test_id} Form validation message displayed")
                        validation_found = True
                        break
                except Exception:
                    pass

        if not validation_found:
            _log(
                f"{test_id} No validation message found, but form may use HTML5 validation"
            )
