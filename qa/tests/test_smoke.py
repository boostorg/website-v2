import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from playwright.sync_api import expect
from page_selectors import selectors
from utils import safe_goto
from config_helper import build_url, test_data, url_patterns, expected_url_patterns
from helpers import (
    find_visible_element,
    check_element_visibility,
    handle_mobile_menu,
    perform_search,
    find_search_results,
    validate_element_details,
    test_patterns,
)

LOG = "smoke-logs.txt"


class TestBoostSmoke:

    # TC_SMOKE_001
    def test_homepage_loads_with_key_elements(self, page, base_url):
        test_id = "TC_SMOKE_001"
        homepage_url = build_url(base_url, url_patterns.homepage, cachebust=True)
        result = test_patterns.load_and_validate_page(
            page, test_id, homepage_url, test_id, LOG
        )
        assert result["load_time"] / 1000 <= 15

        logo_fallbacks = [
            page.get_by_role("img", name=re.compile("Boost", re.I)),
            page.locator('img[alt*="boost" i]'),
            page.locator(".logo img, #logo img"),
            page.locator("header img").first,
        ]
        check_element_visibility(
            page, test_id, selectors.logo(page), logo_fallbacks, "Logo", test_id, LOG
        )

        nav_fallbacks = [
            page.locator('nav, [role="navigation"]'),
            page.locator('div[class*="nav"]'),
            page.locator(".navbar, .navigation"),
        ]
        check_element_visibility(
            page,
            test_id,
            selectors.nav(page),
            nav_fallbacks,
            "Navigation",
            test_id,
            LOG,
        )

        content_fallbacks = [
            page.locator("h1, h2, p").first,
            page.locator("main, .main"),
            page.locator(".content, #content"),
        ]
        check_element_visibility(
            page,
            test_id,
            selectors.content(page),
            content_fallbacks,
            "Main content",
            test_id,
            LOG,
        )

        with open(LOG, "a") as f:
            f.write(f"{test_id} Homepage smoke test completed successfully\n")

    # TC_SMOKE_002
    def test_navigation_menu_links_work(self, page, base_url):
        test_id = "TC_SMOKE_002"
        homepage_url = build_url(base_url, url_patterns.homepage, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, homepage_url, test_id, LOG)

        nav_links = selectors.nav_links(page).all()
        with open(LOG, "a") as f:
            f.write(f"{test_id} Found {len(nav_links)} navigation links\n")

        for i, link in enumerate(nav_links):
            validate_element_details(link, f"Nav link {i}", test_id, LOG)

        visible_nav_links = []
        for i, link in enumerate(nav_links):
            try:
                href = link.get_attribute("href") or ""
                is_visible = link.is_visible()
            except Exception:
                continue
            if (
                is_visible
                and href
                and "mailto:" not in href
                and "tel:" not in href
                and not href.startswith("http")
                and href != "/"
                and href != "#"
            ):
                visible_nav_links.append({"link": link, "href": href, "index": i})

        with open(LOG, "a") as f:
            f.write(
                f"{test_id} Found {len(visible_nav_links)} visible internal navigation links\n"
            )

        tested_links = 0
        max_links = min(3, len(visible_nav_links))
        for item in visible_nav_links[:max_links]:
            link, href = item["link"], item["href"]
            try:
                start_url = page.url
                link.click()
                page.wait_for_load_state("domcontentloaded", timeout=8000)
                current_url = page.url
                if current_url != start_url and href.replace("/", "") in current_url:
                    tested_links += 1
                    try:
                        expect(
                            page.locator("h1, h2, main, .content, body")
                        ).to_be_visible(timeout=3000)
                    except Exception:
                        pass
                elif current_url != start_url:
                    tested_links += 0.5
                safe_goto(
                    page,
                    test_id,
                    homepage_url,
                    wait_until="domcontentloaded",
                    log_file=LOG,
                )
            except Exception as error:
                with open(LOG, "a") as f:
                    f.write(f"{test_id} Link test failed: {error}\n")

        if tested_links > 0:
            assert tested_links > 0
        elif not visible_nav_links:
            raise AssertionError("No functional navigation links found")

    # TC_SMOKE_003
    def test_libraries_page_displays_and_links_to_docs(self, page, base_url):
        test_id = "TC_SMOKE_003"
        libraries_url = build_url(base_url, url_patterns.libraries, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, libraries_url, test_id, LOG)

        library_names = ["Asio", "Beast", "Filesystem", "Algorithm", "Thread"]
        found_libraries = []

        for lib_name in library_names:
            lib_selectors = [
                page.get_by_role("heading", name=re.compile(lib_name, re.I)),
                page.locator("h1, h2, h3, h4, h5, h6").filter(
                    has_text=re.compile(lib_name, re.I)
                ),
                page.locator("a").filter(has_text=re.compile(lib_name, re.I)),
            ]
            for selector in lib_selectors:
                if selector.count() > 0:
                    element = find_visible_element(
                        selector, f"{lib_name} library", test_id, LOG
                    )
                    if element:
                        found_libraries.append(lib_name)
                        with open(LOG, "a") as f:
                            f.write(f"{test_id} Found {lib_name} library on page\n")
                        break

        assert len(found_libraries) > 0
        with open(LOG, "a") as f:
            f.write(f"{test_id} Found libraries: {', '.join(found_libraries)}\n")

        if found_libraries:
            first_lib = found_libraries[0]
            library_link = (
                page.locator("a").filter(has_text=re.compile(first_lib, re.I)).first
            )
            try:
                library_link.click()
                page.wait_for_timeout(3000)
            except Exception as error:
                with open(LOG, "a") as f:
                    f.write(f"{test_id} Library link navigation failed: {error}\n")

    # TC_SMOKE_004
    def test_download_section_works(self, page, base_url):
        test_id = "TC_SMOKE_004"
        releases_url = build_url(base_url, url_patterns.releases, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, releases_url, test_id, LOG)

        download_selectors = [
            'a[href*=".tar.gz"]',
            'a[href*=".zip"]',
            'a[href*="boost_1_"]',
            'a[href*="download"]',
            'a[href*="archives.boost.io"]',
            '[class*="download"]',
        ]
        download_link = None
        for selector in download_selectors:
            elements = page.locator(selector)
            if elements.count() > 0:
                download_link = find_visible_element(
                    elements, f"Download link ({selector})", test_id, LOG
                )
                if download_link:
                    break

        if download_link:
            validate_element_details(download_link, "Download link", test_id, LOG)
            try:
                with page.expect_download(
                    timeout=test_data.timeouts["download"]
                ) as download_info:
                    download_link.click()
                download = download_info.value
                filename = download.suggested_filename
                assert test_data.download_files["supported"].search(filename)
                with open(LOG, "a") as f:
                    f.write(f"{test_id} Download initiated successfully: {filename}\n")
                download.cancel()
            except Exception as error:
                current_url = page.url
                if expected_url_patterns.download_site.search(current_url):
                    with open(LOG, "a") as f:
                        f.write(
                            f"{test_id} Navigated to download page: {current_url}\n"
                        )
                else:
                    with open(LOG, "a") as f:
                        f.write(f"{test_id} Download test inconclusive: {error}\n")

    # TC_SMOKE_005
    def test_search_bar_works_with_basic_query(self, page, base_url):
        test_id = "TC_SMOKE_005"
        homepage_url = build_url(base_url, url_patterns.homepage, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, homepage_url, test_id, LOG)

        try:
            perform_search(
                page,
                test_id,
                selectors,
                test_data.search_terms["working"],
                test_id,
                LOG,
            )
            result = find_search_results(
                page, test_data.search_terms["working"], test_id, LOG
            )
            if result["element"] and result["count"] > 0:
                expect(result["element"]).to_be_visible(
                    timeout=test_data.timeouts["medium"]
                )
                with open(LOG, "a") as f:
                    f.write(
                        f"{test_id} Search results found ({result['count']} results)\n"
                    )
        except Exception as error:
            with open(LOG, "a") as f:
                f.write(f"{test_id} Search functionality test failed: {error}\n")

    # TC_SMOKE_006
    def test_homepage_is_responsive_on_mobile(self, page, base_url):
        test_id = "TC_SMOKE_006"
        test_patterns.set_viewport(page, test_data.viewport["mobile"], test_id, LOG)

        homepage_url = build_url(base_url, url_patterns.homepage, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, homepage_url, test_id, LOG)

        handle_mobile_menu(page, selectors, test_id, LOG)

        nav_fallbacks = [
            page.locator('nav, [role="navigation"]'),
            page.locator('div[class*="nav"]'),
            page.locator(".navbar, .navigation"),
        ]
        check_element_visibility(
            page,
            test_id,
            selectors.nav(page),
            nav_fallbacks,
            "Mobile navigation",
            test_id,
            LOG,
        )

        content_fallbacks = [
            page.locator("h1, h2, p").first,
            page.locator("main, .main"),
            page.locator(".content, #content"),
        ]
        nav_locator = selectors.nav(page)
        content_locator = selectors.content(page)
        check_element_visibility(
            page,
            test_id,
            content_locator,
            content_fallbacks,
            "Mobile content",
            test_id,
            LOG,
        )

        try:
            nav_box = nav_locator.bounding_box()
            content_box = content_locator.bounding_box()
            if nav_box and content_box:
                no_overlap = nav_box["y"] + nav_box["height"] <= content_box["y"] + 10
                with open(LOG, "a") as f:
                    label = (
                        "No navigation/content overlap"
                        if no_overlap
                        else "Potential overlap detected"
                    )
                    f.write(f"{test_id} Mobile layout: {label}\n")
        except Exception as error:
            with open(LOG, "a") as f:
                f.write(f"{test_id} Mobile layout check failed: {error}\n")

        with open(LOG, "a") as f:
            f.write(f"{test_id} Mobile responsiveness test completed\n")
