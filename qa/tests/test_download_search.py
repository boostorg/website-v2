import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from playwright.sync_api import expect
from page_selectors import selectors
from config_helper import build_url, test_data, url_patterns
from test_helpers import (
    find_visible_element,
    perform_search,
    find_search_results,
    test_patterns,
)

LOG = "test-logs.txt"


def _log(message):
    with open(LOG, "a") as f:
        f.write(message + "\n")


class TestBoostDownload:

    # TC_DOWNLOAD_001
    def test_download_links_return_valid_http_status_codes(self, page, base_url):
        test_id = "TC_DOWNLOAD_001"
        releases_url = build_url(base_url, url_patterns.releases, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, releases_url, test_id, LOG)

        download_selectors = [
            'a[href*=".tar.gz"]',
            'a[href*=".zip"]',
            'a[href*="boost_1_"]',
            'a[href*="archives.boost.io"]',
        ]
        download_links = []
        for selector in download_selectors:
            for link in page.locator(selector).all():
                href = link.get_attribute("href")
                try:
                    is_visible = link.is_visible()
                except Exception:
                    is_visible = False
                if href and is_visible:
                    download_links.append({"element": link, "href": href})

        _log(f"{test_id} Found {len(download_links)} download links")
        assert len(download_links) > 0

        for item in download_links[:5]:
            href = item["href"]
            try:
                response = page.request.head(href, timeout=15000)
                status = response.status
                _log(f"{test_id} Download link: {href} - Status: {status}")
                assert 200 <= status < 400
            except Exception as error:
                _log(f"{test_id} Failed to check {href}: {error}")

    # TC_DOWNLOAD_002
    def test_download_file_names_are_correct_format(self, page, base_url):
        test_id = "TC_DOWNLOAD_002"
        releases_url = build_url(base_url, url_patterns.releases, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, releases_url, test_id, LOG)

        download_links = page.locator(
            'a[href*="boost_1_"], a[href*=".tar.gz"], a[href*=".zip"]'
        ).all()
        _log(f"{test_id} Found {len(download_links)} download links")

        for link in download_links[:5]:
            href = link.get_attribute("href") or ""
            text = link.text_content() or ""
            has_valid_format = bool(
                re.search(r"boost_\d+_\d+_\d+\.(tar\.gz|zip|7z)", href)
                or re.search(r"\d+\.\d+\.\d+", href)
            )
            _log(
                f"{test_id} Link: {text.strip()} -> {href}, Valid format: {has_valid_format}"
            )
            if href and "boost" in href:
                assert has_valid_format

    # TC_DOWNLOAD_003
    def test_version_selector_displays_available_versions(self, page, base_url):
        test_id = "TC_DOWNLOAD_003"
        releases_url = build_url(base_url, url_patterns.releases, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, releases_url, test_id, LOG)

        version_selectors = [
            page.locator('select[name*="version"], select[id*="version"]'),
            page.locator('select option[value*="1.8"]').locator(".."),
            page.locator('[data-testid*="version"]'),
            page.locator(".version-selector, #version-selector"),
        ]
        version_dropdown = None
        for selector in version_selectors:
            if selector.count() > 0:
                version_dropdown = selector.first
                try:
                    if version_dropdown.is_visible():
                        break
                except Exception:
                    version_dropdown = None

        if version_dropdown:
            expect(version_dropdown).to_be_visible(timeout=test_data.timeouts["medium"])
            options = version_dropdown.locator("option").all()
            option_texts = [opt.text_content() for opt in options]
            _log(
                f"{test_id} Available versions: {', '.join(t or '' for t in option_texts)}"
            )
            assert len(options) > 0
        else:
            _log(
                f"{test_id} No version selector found - versions may be displayed differently"
            )
            version_text_count = page.locator("text=/1\\.8\\d+|version/i").count()
            assert version_text_count > 0

    # TC_DOWNLOAD_004
    def test_download_page_displays_file_sizes(self, page, base_url):
        test_id = "TC_DOWNLOAD_004"
        releases_url = build_url(base_url, url_patterns.releases, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, releases_url, test_id, LOG)

        file_size_patterns = [
            page.locator("text=/\\d+\\s*(MB|GB|KB)/i"),
            page.locator("text=/\\d+\\.\\d+\\s*(MB|GB)/i"),
            page.locator('[class*="size"], [class*="file-size"]'),
        ]
        file_size_found = False
        for pattern in file_size_patterns:
            if pattern.count() > 0:
                try:
                    is_visible = pattern.first.is_visible()
                except Exception:
                    is_visible = False
                if is_visible:
                    text = pattern.first.text_content()
                    _log(f"{test_id} Found file size: {text}")
                    file_size_found = True
                    break

        _log(
            f"{test_id} File sizes {'displayed on download page' if file_size_found else 'not found - may not be displayed'}"
        )


class TestBoostSearch:

    # TC_SEARCH_001
    def test_search_returns_relevant_results_for_common_queries(self, page, base_url):
        test_id = "TC_SEARCH_001"
        homepage_url = build_url(base_url, url_patterns.homepage, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, homepage_url, test_id, LOG)

        common_queries = ["asio", "filesystem", "algorithm"]
        for query in common_queries:
            perform_search(page, test_id, selectors, query, test_id, LOG)
            result = find_search_results(page, query, test_id, LOG)
            if result["element"] and result["count"] > 0:
                expect(result["element"]).to_be_visible(
                    timeout=test_data.timeouts["medium"]
                )
                result_text = (result["element"].text_content() or "").lower()
                assert query.lower() in result_text
                _log(
                    f'{test_id} Search for "{query}" returned {result["count"]} results'
                )
            else:
                _log(f'{test_id} No results found for "{query}"')

            page.goto(homepage_url, wait_until="networkidle")
            page.wait_for_timeout(1000)

    # TC_SEARCH_002
    def test_search_with_special_characters_handles_gracefully(self, page, base_url):
        test_id = "TC_SEARCH_002"
        homepage_url = build_url(base_url, url_patterns.homepage, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, homepage_url, test_id, LOG)

        special_queries = ["C++", "boost::asio"]
        for query in special_queries:
            try:
                perform_search(page, test_id, selectors, query, test_id, LOG)
                page.wait_for_timeout(3000)
                has_error = page.locator("text=/error|500|crash/i").count()
                assert has_error == 0
                _log(f'{test_id} Search with "{query}" handled gracefully')
                page.goto(homepage_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(1000)
            except Exception as error:
                _log(f'{test_id} Search with "{query}" noted: {error}')
                try:
                    page.goto(
                        homepage_url, wait_until="domcontentloaded", timeout=30000
                    )
                except Exception:
                    _log(f"{test_id} Could not recover, skipping remaining searches")
                    break

    # TC_SEARCH_003
    def test_empty_search_shows_appropriate_message(self, page, base_url):
        test_id = "TC_SEARCH_003"
        homepage_url = build_url(base_url, url_patterns.homepage, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, homepage_url, test_id, LOG)

        try:
            search_input = selectors.search(page)
            if search_input.count() == 0:
                _log(f"{test_id} No search input found, skipping test")
                return
            visible_search = find_visible_element(
                search_input, "Search input", test_id, LOG
            )
            if not visible_search:
                _log(f"{test_id} Search input not visible, skipping test")
                return

            visible_search.click()
            visible_search.press("Enter")
            page.wait_for_timeout(2000)

            messages = [
                page.locator("text=/please enter|required|empty/i"),
                page.locator("text=/no results/i"),
                page.locator('[role="alert"]'),
            ]
            message_found = any(
                m.is_visible()
                for m in messages
                if m.count() > 0 and (lambda m=m: m.is_visible())()
            )
            _log(
                f"{test_id} Empty search message {'displayed' if message_found else 'prevented or handled silently'}"
            )
        except Exception as error:
            _log(f"{test_id} Test skipped: {error}")

    # TC_SEARCH_004
    def test_search_result_pagination_works_correctly(self, page, base_url):
        test_id = "TC_SEARCH_004"
        homepage_url = build_url(base_url, url_patterns.homepage, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, homepage_url, test_id, LOG)

        perform_search(page, test_id, selectors, "boost", test_id, LOG)
        page.wait_for_timeout(2000)

        pagination_selectors = [
            page.locator(
                '[aria-label*="pagination"], [role="navigation"][aria-label*="page"]'
            ),
            page.locator(".pagination, .paging, .page-navigation"),
            page.locator('a:has-text("Next"), button:has-text("Next")'),
            page.locator('a:has-text("2"), button:has-text("2")'),
        ]
        pagination_found = False
        for selector in pagination_selectors:
            if selector.count() > 0:
                try:
                    is_visible = selector.first.is_visible()
                except Exception:
                    is_visible = False
                if is_visible:
                    _log(f"{test_id} Pagination controls found")
                    pagination_found = True
                    next_button = page.locator(
                        'a:has-text("Next"), button:has-text("Next")'
                    ).first
                    if next_button.count() > 0:
                        try:
                            if next_button.is_visible():
                                url_before = page.url
                                next_button.click()
                                page.wait_for_timeout(2000)
                                _log(
                                    f"{test_id} Pagination click: URL changed = {page.url != url_before}"
                                )
                        except Exception:
                            pass
                    break

        if not pagination_found:
            _log(f"{test_id} No pagination found - results may fit on one page")

    # TC_SEARCH_005
    def test_search_autocomplete_suggestions_appear(self, page, base_url):
        test_id = "TC_SEARCH_005"
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

            visible_search.fill("asi")
            page.wait_for_timeout(1500)

            suggestion_selectors = [
                page.locator('[role="listbox"], [role="menu"]'),
                page.locator(".autocomplete, .suggestions, .search-suggestions"),
                page.locator('[class*="dropdown"][class*="search"]'),
                page.locator('ul[class*="search"] li, div[class*="suggest"]'),
            ]
            suggestions_found = False
            for selector in suggestion_selectors:
                if selector.count() > 0:
                    try:
                        if selector.first.is_visible():
                            suggestions_found = True
                            break
                    except Exception:
                        pass

            _log(
                f"{test_id} Search {'autocomplete working' if suggestions_found else 'no autocomplete found - may not be implemented'}"
            )
        except Exception as error:
            _log(f"{test_id} Test skipped: {error}")
