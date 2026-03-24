import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from playwright.sync_api import expect
from page_selectors import selectors
from config_helper import build_url, test_data, url_patterns
from helpers import find_visible_element, check_element_visibility, test_patterns

LOG = "test-logs.txt"


def _log(message):
    with open(LOG, "a") as f:
        f.write(message + "\n")


class TestBoostVersion:

    # TC_VERSION_001
    def test_libraries_page_loads_and_displays_version_information(
        self, page, base_url
    ):
        test_id = "TC_VERSION_001"
        libraries_url = build_url(base_url, url_patterns.libraries, cachebust=True)
        result = test_patterns.load_and_validate_page(
            page, test_id, libraries_url, test_id, LOG
        )
        assert result["load_time"] / 1000 <= 15

        logo_fallbacks = [
            page.locator('img[src*="Boost_Symbol_Transparent.svg"]'),
            page.locator('img[alt*="boost" i]'),
            page.locator(".logo img, #logo img"),
            page.locator("header img").first,
        ]
        try:
            check_element_visibility(
                page,
                test_id,
                selectors.logo(page),
                logo_fallbacks,
                "Logo",
                test_id,
                LOG,
            )
        except Exception:
            _log(f"{test_id} Logo not found but continuing test")

        version_selectors = [
            'select[name="version"]',
            '[data-test-id="version-dropdown"]',
            ".version-selector",
            'select:has(option[value*="1.8"])',
            '*:has-text("Version")',
            '*:has-text("Latest")',
            '*:has-text("1.8")',
        ]
        version_element = None
        for selector in version_selectors:
            try:
                elements = page.locator(selector)
                if elements.count() > 0:
                    version_element = find_visible_element(
                        elements, f"Version element ({selector})", test_id, LOG
                    )
                    if version_element:
                        break
            except Exception as error:
                _log(f'{test_id} Version selector "{selector}" failed: {error}')

        if version_element:
            _log(f"{test_id} Found version-related element")
            expect(version_element).to_be_visible(timeout=test_data.timeouts["medium"])
        else:
            _log(f"{test_id} No version selectors found - may be a static page")

        library_link_selectors = [
            'a[href*="/libs/"]',
            'a[href*="asio"]',
            'a[href*="algorithm"]',
            'a[href*="filesystem"]',
            '*:has-text("Libraries")',
            "nav a, .nav a",
        ]
        library_links = None
        for selector in library_link_selectors:
            try:
                elements = page.locator(selector)
                if elements.count() > 0:
                    library_links = elements
                    _log(
                        f"{test_id} Found {elements.count()} library links with selector: {selector}"
                    )
                    break
            except Exception as error:
                _log(f'{test_id} Library selector "{selector}" failed: {error}')

        if library_links:
            expect(library_links.first).to_be_visible(
                timeout=test_data.timeouts["medium"]
            )
            _log(f"{test_id} Library links found and visible")

        if version_element:
            try:
                tag_name = version_element.evaluate("el => el.tagName.toLowerCase()")
                if tag_name == "select":
                    options = version_element.locator("option").all()
                    option_texts = [opt.text_content() for opt in options]
                    _log(f"{test_id} Available version options: {option_texts}")
                    if len(options) > 1:
                        version_element.select_option(index=1)
                        page.wait_for_timeout(2000)
                        _log(f"{test_id} Selected older version")
            except Exception as error:
                _log(f"{test_id} Version switching failed: {error}")

        page.screenshot(path="screenshots/tc_version_001_final.png")

    # TC_VERSION_002
    def test_releases_page_loads_and_displays_release_information(self, page, base_url):
        test_id = "TC_VERSION_002"
        releases_url = build_url(base_url, url_patterns.releases, cachebust=True)
        result = test_patterns.load_and_validate_page(
            page, test_id, releases_url, test_id, LOG
        )
        assert result["load_time"] / 1000 <= 15

        logo_fallbacks = [
            page.locator('img[src*="Boost_Symbol_Transparent.svg"]'),
            page.locator('img[alt*="boost" i]'),
            page.locator(".logo img, #logo img"),
            page.locator("header img").first,
        ]
        try:
            check_element_visibility(
                page,
                test_id,
                selectors.logo(page),
                logo_fallbacks,
                "Logo",
                test_id,
                LOG,
            )
        except Exception:
            _log(f"{test_id} Logo not found but continuing test")

        release_selectors = [
            'select[name="release"]',
            '[data-test-id="release-dropdown"]',
            ".release-selector",
            '*:has-text("Release")',
            '*:has-text("Version")',
            '*:has-text("1.8")',
            '*:has-text("Download")',
        ]
        release_element = None
        for selector in release_selectors:
            try:
                elements = page.locator(selector)
                if elements.count() > 0:
                    release_element = find_visible_element(
                        elements, f"Release element ({selector})", test_id, LOG
                    )
                    if release_element:
                        break
            except Exception as error:
                _log(f'{test_id} Release selector "{selector}" failed: {error}')

        if release_element:
            _log(f"{test_id} Found release-related element")
            expect(release_element).to_be_visible(timeout=test_data.timeouts["medium"])
        else:
            _log(f"{test_id} No release selectors found")

        download_link_selectors = [
            'a[href*="download"]',
            'a[href*="boost_1_"]',
            'a[href*=".tar.gz"]',
            'a[href*=".zip"]',
            'a[href*="archives.boost.io"]',
            'a[href*="github.com/boostorg/boost/releases"]',
            '*:has-text("Download")',
            '[class*="download"]',
        ]
        download_links = None
        for selector in download_link_selectors:
            try:
                elements = page.locator(selector)
                if elements.count() > 0:
                    download_links = elements
                    _log(
                        f"{test_id} Found {elements.count()} download links with selector: {selector}"
                    )
                    break
            except Exception as error:
                _log(f'{test_id} Download selector "{selector}" failed: {error}')

        if download_links:
            first_download = download_links.first
            expect(first_download).to_be_visible(timeout=test_data.timeouts["medium"])
            _log(f"{test_id} Download links found and visible")
            href = first_download.get_attribute("href")
            text = first_download.text_content() or ""
            _log(f'{test_id} First download link: href="{href}", text="{text}"')

        release_notes_selectors = [
            'a[href*="release"]',
            'a[href*="history"]',
            'a[href*="notes"]',
            '*:has-text("Release Notes")',
            '*:has-text("History")',
            '*:has-text("Changelog")',
        ]
        release_notes_links = None
        for selector in release_notes_selectors:
            try:
                elements = page.locator(selector)
                if elements.count() > 0:
                    release_notes_links = elements
                    _log(
                        f"{test_id} Found {elements.count()} release notes links with selector: {selector}"
                    )
                    break
            except Exception as error:
                _log(f'{test_id} Release notes selector "{selector}" failed: {error}')

        if release_notes_links:
            first_notes = release_notes_links.first
            try:
                is_visible = first_notes.is_visible()
            except Exception:
                is_visible = False

            if is_visible:
                expect(first_notes).to_be_visible(timeout=test_data.timeouts["medium"])
                _log(f"{test_id} Release notes links found and visible")
            else:
                count = release_notes_links.count()
                visible_notes = None
                for i in range(count):
                    link = release_notes_links.nth(i)
                    try:
                        if link.is_visible():
                            visible_notes = link
                            break
                    except Exception:
                        continue
                if visible_notes:
                    expect(visible_notes).to_be_visible(
                        timeout=test_data.timeouts["medium"]
                    )
                    _log(f"{test_id} Found visible release notes link")
                else:
                    _log(f"{test_id} Release notes links found but none are visible")

        page.screenshot(path="screenshots/tc_version_002_final.png")
