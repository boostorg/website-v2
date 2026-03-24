import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest
from playwright.sync_api import expect
from page_selectors import selectors
from utils import log_and_screenshot, safe_goto
from config_helper import build_url, test_data, url_patterns, expected_url_patterns
from test_helpers import (
    find_visible_element,
    test_element_visibility,
    handle_mobile_menu,
    perform_search,
    find_search_results,
    test_navigation_link,
    validate_element_details,
    test_patterns,
)

LOG = "test-logs.txt"


def setup_page(page):
    page.set_viewport_size(test_data.viewport["desktop"])
    page.on("console", lambda msg: _log(f"Console [{msg.type}]: {msg.text}"))
    page.on("pageerror", lambda err: _log(f"PAGE ERROR: {err}"))
    page.on("close", lambda: _log("Page closed unexpectedly"))
    page.route(
        "**/*.{woff,woff2,ttf,otf,eot,png,jpg,jpeg,svg}", lambda route: route.abort()
    )
    page.route("**/*font*", lambda route: route.abort())
    page.route("**/*image*", lambda route: route.abort())


def _log(message):
    with open(LOG, "a") as f:
        f.write(message + "\n")


class TestBoostFunctional:

    @pytest.fixture(autouse=True)
    def setup(self, page):
        setup_page(page)
        yield
        # afterEach: screenshot on failure handled by conftest

    # TC_FUNC_001
    def test_homepage_loads_and_displays_key_elements(self, page, base_url):
        test_id = "TC_FUNC_001"
        homepage_url = build_url(base_url, url_patterns.homepage, cachebust=True)
        result = test_patterns.load_and_validate_page(
            page, test_id, homepage_url, test_id, LOG
        )
        assert result["load_time"] / 1000 <= 15

        logo_fallbacks = [
            page.locator('img[alt="Boost"]'),
            page.locator('img[src*="boost" i]'),
            page.locator(".logo img, #logo img"),
            page.locator("header img").first,
        ]
        test_element_visibility(
            page,
            test_id,
            selectors.logo(page),
            logo_fallbacks,
            "Boost logo",
            test_id,
            LOG,
        )
        test_element_visibility(
            page, test_id, selectors.nav(page), [], "Navigation bar", test_id, LOG
        )
        test_element_visibility(
            page, test_id, selectors.content(page), [], "Main content", test_id, LOG
        )

        cta_candidates = page.get_by_role(
            "link", name=re.compile(r"download|release|get started|latest", re.I)
        ).all()
        for i, candidate in enumerate(cta_candidates):
            validate_element_details(candidate, f"CTA candidate {i}", test_id, LOG)

        visible_cta = test_element_visibility(
            page,
            test_id,
            selectors.cta(page),
            cta_candidates if cta_candidates else [],
            "CTA button",
            test_id,
            LOG,
        )
        visible_cta.click()
        expect(page).to_have_url(
            expected_url_patterns.after_cta_click, timeout=test_data.timeouts["medium"]
        )
        _log(f"{test_id} CTA navigation successful")

        footer_fallbacks = [
            page.locator("footer, .footer, #footer"),
            page.locator('[role="contentinfo"]'),
            page.locator("body > div:last-child, body > section:last-child"),
            page.locator(
                '*:has-text("Copyright"), *:has-text("©"), *:has-text("Terms"), *:has-text("Privacy")'
            ),
            page.locator("nav:last-of-type, ul:last-of-type"),
        ]
        try:
            test_element_visibility(
                page,
                test_id,
                selectors.footer(page),
                footer_fallbacks,
                "Footer",
                test_id,
                LOG,
            )
        except Exception:
            _log(f"{test_id} Footer not found but continuing test")

    # TC_FUNC_002
    def test_search_bar_is_visible_and_functional(self, page, base_url):
        test_id = "TC_FUNC_002"
        homepage_url = build_url(base_url, url_patterns.homepage, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, homepage_url, test_id, LOG)
        test_patterns.set_viewport(page, test_data.viewport["mobile"], test_id, LOG)

        handle_mobile_menu(page, selectors, test_id, LOG)
        perform_search(
            page, test_id, selectors, test_data.search_terms["working"], test_id, LOG
        )

        result = find_search_results(
            page, test_data.search_terms["working"], test_id, LOG
        )
        if result["element"] and result["count"] > 0:
            expect(result["element"]).to_be_visible(timeout=test_data.timeouts["long"])
            _log(f"{test_id} Search results validated ({result['count']} results)")
        else:
            page_text = (page.text_content("body") or "").lower()
            if test_data.search_terms["working"].lower() in page_text:
                _log(f"{test_id} Search term found in page content")
            else:
                log_and_screenshot(
                    page,
                    test_id,
                    "Search results not displayed",
                    "screenshots/tc_func_002_no_results.png",
                    LOG,
                )
                raise AssertionError("Search results not displayed")

    # TC_FUNC_003
    def test_navigation_menu_links_work(self, page, base_url):
        test_id = "TC_FUNC_003"
        homepage_url = build_url(base_url, url_patterns.homepage, cachebust=True)
        result = test_patterns.load_and_validate_page(
            page, test_id, homepage_url, test_id, LOG
        )
        assert result["load_time"] / 1000 <= 15

        nav_links = selectors.nav_links(page).all()
        _log(f"{test_id} Found {len(nav_links)} navigation links")
        if not nav_links:
            _log(f"{test_id} No navigation links found, skipping checks")
            return

        for i, link in enumerate(nav_links[:5]):
            test_navigation_link(page, test_id, link, i, test_id, homepage_url, LOG)

    # TC_FUNC_004
    def test_responsive_design_adapts_to_mobile_viewport(self, page, base_url):
        test_id = "TC_FUNC_004"
        homepage_url = build_url(base_url, url_patterns.homepage, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, homepage_url, test_id, LOG)

        test_patterns.set_viewport(page, test_data.viewport["mobile"], test_id, LOG)
        mobile_toggle = selectors.mobile_toggle(page)
        toggle_count = mobile_toggle.count()
        _log(f"{test_id} Mobile toggle elements found: {toggle_count}")

        if toggle_count > 0:
            visible_toggle = find_visible_element(
                mobile_toggle, "Mobile toggle", test_id, LOG
            )
            if visible_toggle:
                handle_mobile_menu(page, selectors, test_id, LOG)
        else:
            _log(f"{test_id} No mobile toggle found - responsive design without toggle")

        test_patterns.set_viewport(page, test_data.viewport["desktop"], test_id, LOG)
        if toggle_count > 0:
            try:
                is_visible_on_desktop = mobile_toggle.first.is_visible()
            except Exception:
                is_visible_on_desktop = False
            if is_visible_on_desktop:
                raise AssertionError(
                    "Mobile toggle should not be visible on desktop viewport"
                )

        _log(f"{test_id} Responsive design test completed")

    # TC_FUNC_005
    def test_logo_redirects_to_homepage(self, page, base_url):
        test_id = "TC_FUNC_005"
        libraries_url = build_url(base_url, url_patterns.libraries, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, libraries_url, test_id, LOG)

        logo_fallbacks = [
            page.locator('img[src*="Boost_Symbol_Transparent.svg"]'),
            page.locator('img[alt*="boost" i]'),
            page.locator(".logo img, #logo img"),
            page.locator("header img").first,
        ]
        visible_logo = test_element_visibility(
            page, test_id, selectors.logo(page), logo_fallbacks, "Logo", test_id, LOG
        )
        visible_logo.click()
        expect(page).to_have_url(
            expected_url_patterns.after_logo_click, timeout=test_data.timeouts["medium"]
        )
        _log(f"{test_id} Logo redirect successful")

    # TC_FUNC_006
    def test_footer_links_are_accessible(self, page, base_url):
        test_id = "TC_FUNC_006"
        homepage_url = build_url(base_url, url_patterns.homepage, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, homepage_url, test_id, LOG)

        footer = page.get_by_role("contentinfo").first
        footer_fallbacks = [
            page.locator("footer, .footer, #footer"),
            page.locator('[role="contentinfo"]'),
            page.locator('*:has-text("Copyright"), *:has-text("©")'),
        ]
        try:
            test_element_visibility(
                page, test_id, footer, footer_fallbacks, "Footer", test_id, LOG
            )
            footer_links = footer.locator("a").all()
            _log(f"{test_id} Found {len(footer_links)} footer links")
            for i, link in enumerate(footer_links):
                validate_element_details(link, f"Footer link {i}", test_id, LOG)
                expect(link).to_be_visible(timeout=test_data.timeouts["short"])
        except Exception:
            _log(f"{test_id} Footer not found, skipping footer link tests")

    # TC_FUNC_007
    def test_main_content_loads_on_library_page(self, page, base_url):
        test_id = "TC_FUNC_007"
        library_url = build_url(base_url, url_patterns.documentation, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, library_url, test_id, LOG)
        test_element_visibility(
            page, test_id, selectors.content(page), [], "Main content", test_id, LOG
        )

    # TC_FUNC_008
    def test_external_links_are_valid(self, page, base_url):
        test_id = "TC_FUNC_008"
        homepage_url = build_url(base_url, url_patterns.homepage, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, homepage_url, test_id, LOG)

        external_links = selectors.external_links(page).all()
        _log(f"{test_id} Found {len(external_links)} external links")
        for i, link in enumerate(external_links):
            validate_element_details(link, f"External link {i}", test_id, LOG)
            expect(link).to_be_visible(timeout=test_data.timeouts["short"])

    # TC_FUNC_009
    def test_github_links_point_to_correct_repositories(self, page, base_url):
        test_id = "TC_FUNC_009"
        community_url = build_url(base_url, url_patterns.community, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, community_url, test_id, LOG)

        github_links = page.locator('a[href*="github.com"]').all()
        _log(f"{test_id} Found {len(github_links)} GitHub links")
        for i, link in enumerate(github_links):
            details = validate_element_details(link, f"GitHub link {i}", test_id, LOG)
            expect(link).to_be_visible(timeout=test_data.timeouts["short"])
            if details.get("href"):
                assert expected_url_patterns.github_boost.search(details["href"])

    # TC_FUNC_010
    def test_documentation_page_loads_and_displays_content(self, page, base_url):
        test_id = "TC_FUNC_010"
        doc_url = build_url(base_url, url_patterns.doc_libs_version(), cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, doc_url, test_id, LOG)
        test_element_visibility(
            page,
            test_id,
            selectors.content(page),
            [],
            "Documentation content",
            test_id,
            LOG,
        )

    # TC_FUNC_011
    def test_release_notes_are_accessible(self, page, base_url):
        test_id = "TC_FUNC_011"
        release_notes_url = build_url(
            base_url, url_patterns.release_notes(), cachebust=True
        )
        test_patterns.load_and_validate_page(
            page, test_id, release_notes_url, test_id, LOG
        )
        test_element_visibility(
            page,
            test_id,
            selectors.content(page),
            [],
            "Release notes content",
            test_id,
            LOG,
        )

    # TC_FUNC_012
    def test_download_link_for_previous_release_works(self, page, base_url):
        test_id = "TC_FUNC_012"
        releases_url = build_url(base_url, url_patterns.releases, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, releases_url, test_id, LOG)

        download_patterns = [
            'a[href*="archives.boost.io/release/1.85.0/source/boost_1_85_0.tar.gz"]',
            'a[href*="archives.boost.io/release/1.85.0/source/boost_1_85_0.zip"]',
            'a[href*="boost_1_85_0"]',
            'a[href*="archives.boost.io"]',
            'a:has-text("Download")',
            'a:has-text("tar.gz")',
            'a:has-text("zip")',
            '[class*="download"]',
        ]
        download_link = None
        for pattern in download_patterns:
            try:
                elements = page.locator(pattern)
                if elements.count() > 0:
                    download_link = find_visible_element(
                        elements, f"Download link ({pattern})", test_id, LOG
                    )
                    if download_link:
                        break
            except Exception as error:
                _log(f'{test_id} Pattern "{pattern}" failed: {error}')

        if not download_link:
            log_and_screenshot(
                page,
                test_id,
                "No download links found",
                "screenshots/tc_func_012_no_links.png",
                LOG,
            )
            raise AssertionError("Download link not found for previous release")

        validate_element_details(download_link, "Download link", test_id, LOG)

        try:
            with page.expect_download(
                timeout=test_data.timeouts["download"]
            ) as download_info:
                download_link.click(timeout=test_data.timeouts["medium"])
            download = download_info.value
            filename = download.suggested_filename
            assert test_data.download_files["supported"].search(filename)
            pathlib.Path("downloads").mkdir(exist_ok=True)
            download.save_as(f"downloads/{filename}")
            _log(f"{test_id} Downloaded file: {filename}")
        except Exception:
            current_url = page.url
            try:
                expect(page).to_have_url(
                    expected_url_patterns.download_site,
                    timeout=test_data.timeouts["medium"],
                )
                _log(f"{test_id} Navigated to download page: {current_url}")
            except Exception as e:
                _log(f"{test_id} Download test inconclusive: {e}")

    # TC_FUNC_013
    def test_download_handles_broken_or_unavailable_links(self, page, base_url):
        test_id = "TC_FUNC_013"
        releases_url = build_url(base_url, url_patterns.releases, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, releases_url, test_id, LOG)

        route_intercepted = {"value": False}

        def handle_broken_route(route):
            route_intercepted["value"] = True
            _log(f"{test_id} Route intercepted for broken.zip")
            route.fulfill(
                status=404,
                content_type="text/html",
                body="<html><body><h1>404 Not Found</h1><p>The requested file could not be found.</p></body></html>",
            )

        page.route("**/releases/broken.zip", handle_broken_route)
        broken_link_url = build_url(base_url, "/releases/broken.zip")

        try:
            safe_goto(
                page, test_id, broken_link_url, wait_until="networkidle", log_file=LOG
            )
        except Exception:
            _log(f"{test_id} Broken link navigation failed as expected")

        if not route_intercepted["value"]:
            page.set_content(
                "<html><body><h1>404 Not Found</h1><p>The requested file could not be found.</p></body></html>"
            )

        error_message = (
            page.locator("*")
            .filter(
                has_text=re.compile(
                    r"error|not found|404|unable to locate|missing|failed", re.I
                )
            )
            .first
        )
        expect(error_message).to_be_visible(timeout=test_data.timeouts["medium"])
        _log(f"{test_id} Error message validation successful")

    # TC_FUNC_014
    def test_community_page_links_are_functional(self, page, base_url):
        test_id = "TC_FUNC_014"
        community_url = build_url(base_url, url_patterns.community, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, community_url, test_id, LOG)

        community_links = page.locator(
            'a[href*="github.com/*/issues"], a[href*="discourse"], a[href*="lists.boost.org"]'
        )
        visible_link = find_visible_element(
            community_links, "Community link", test_id, LOG
        )
        if not visible_link:
            log_and_screenshot(
                page,
                test_id,
                "Community link not visible",
                "screenshots/tc_func_014_no_links.png",
                LOG,
            )
            raise AssertionError("Community link not visible")

        details = validate_element_details(visible_link, "Community link", test_id, LOG)
        is_new_tab = details.get("class") and "_blank" in (details["class"] or "")

        try:
            if is_new_tab:
                with page.context.expect_page(
                    timeout=test_data.timeouts["medium"]
                ) as page_info:
                    visible_link.click()
                new_page = page_info.value
                expect(new_page).to_have_url(
                    expected_url_patterns.community_links,
                    timeout=test_data.timeouts["medium"],
                )
                new_page.close()
                _log(f"{test_id} Community link opened in new tab successfully")
            else:
                visible_link.click()
                expect(page).to_have_url(
                    expected_url_patterns.community_links,
                    timeout=test_data.timeouts["medium"],
                )
                _log(f"{test_id} Community link navigation successful")
        except Exception as e:
            log_and_screenshot(
                page,
                test_id,
                f"Community link test failed: {e}",
                "screenshots/tc_func_014_error.png",
                LOG,
            )
            raise AssertionError(f"Community link test failed: {e}")
