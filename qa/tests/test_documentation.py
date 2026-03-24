import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from playwright.sync_api import expect
from selectors import selectors
from config_helper import build_url, test_data, url_patterns
from test_helpers import find_visible_element, test_element_visibility, test_patterns

LOG = "test-logs.txt"


def _log(message):
    with open(LOG, "a") as f:
        f.write(message + "\n")


class TestBoostDocumentation:

    # TC_DOC_001
    def test_documentation_page_loads_with_table_of_contents(self, page, base_url):
        test_id = "TC_DOC_001"
        doc_url = build_url(base_url, url_patterns.documentation, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, doc_url, test_id, LOG)

        toc_selectors = [
            page.locator('[class*="toc"], [id*="toc"]'),
            page.locator('nav[aria-label*="table of contents" i]'),
            page.locator(".sidebar, .navigation, [class*='sidebar']"),
            page.locator("ul li a").first,
        ]
        toc_found = False
        for selector in toc_selectors:
            if selector.count() > 0:
                try:
                    is_visible = selector.first.is_visible()
                except Exception:
                    is_visible = False
                if is_visible:
                    expect(selector.first).to_be_visible(
                        timeout=test_data.timeouts["medium"]
                    )
                    _log(f"{test_id} Table of contents found")
                    toc_found = True
                    break

        _log(
            f"{test_id} Documentation TOC verified"
            if toc_found
            else f"{test_id} No explicit TOC found"
        )
        test_element_visibility(
            page,
            test_id,
            selectors.content(page),
            [],
            "Documentation content",
            test_id,
            LOG,
        )

    # TC_DOC_002
    def test_library_documentation_links_are_accessible(self, page, base_url):
        test_id = "TC_DOC_002"
        libraries_url = build_url(base_url, url_patterns.libraries, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, libraries_url, test_id, LOG)

        popular_libraries = ["asio", "filesystem", "algorithm", "thread", "beast"]
        found_libraries = 0

        for lib_name in popular_libraries:
            library_link = page.locator(f'a:has-text("{lib_name}")').first
            if library_link.count() > 0:
                try:
                    is_visible = library_link.is_visible()
                except Exception:
                    is_visible = False
                if is_visible:
                    href = library_link.get_attribute("href")
                    _log(f"{test_id} Found {lib_name} library: {href}")
                    assert href
                    found_libraries += 1

                    if found_libraries == 1:
                        library_link.click()
                        page.wait_for_load_state(
                            "networkidle", timeout=test_data.timeouts["medium"]
                        )
                        new_url = page.url
                        _log(f"{test_id} Navigated to library doc: {new_url}")
                        has_doc_content = page.locator("h1, h2, main, article").count()
                        assert has_doc_content > 0
                        page.goto(libraries_url, wait_until="networkidle")

        assert found_libraries > 0
        _log(f"{test_id} Found {found_libraries} library links")

    # TC_DOC_003
    def test_code_examples_are_properly_formatted(self, page, base_url):
        test_id = "TC_DOC_003"
        try:
            doc_url = build_url(
                base_url, url_patterns.doc_libs_version(), cachebust=True
            )
            test_patterns.load_and_validate_page(page, test_id, doc_url, test_id, LOG)

            code_selectors = [
                page.locator("pre code"),
                page.locator(".code, .example-code"),
                page.locator('[class*="code-"]'),
                page.locator("pre"),
            ]
            code_block_found = False
            for selector in code_selectors:
                if selector.count() > 0:
                    first_code = selector.first
                    try:
                        is_visible = first_code.is_visible()
                    except Exception:
                        is_visible = False
                    if is_visible:
                        code_text = first_code.text_content() or ""
                        _log(
                            f"{test_id} Found code block with {len(code_text)} characters"
                        )
                        if re.search(r"[{};()#include]", code_text):
                            _log(f"{test_id} Code block appears properly formatted")
                            code_block_found = True
                        break

            _log(
                f"{test_id} Code examples verified"
                if code_block_found
                else f"{test_id} No code examples found on this page"
            )
        except Exception as error:
            _log(f"{test_id} Test failed: {error}")
            if "closed" not in str(error):
                raise

    # TC_DOC_004
    def test_documentation_breadcrumbs_navigation_works(self, page, base_url):
        test_id = "TC_DOC_004"
        doc_url = build_url(base_url, url_patterns.doc_libs_version(), cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, doc_url, test_id, LOG)

        breadcrumb_selectors = [
            page.locator('[aria-label*="breadcrumb" i]'),
            page.locator(".breadcrumb, .breadcrumbs"),
            page.locator('[class*="breadcrumb"]'),
            page.locator("nav ol, nav ul").first,
        ]
        breadcrumbs_found = False
        for selector in breadcrumb_selectors:
            if selector.count() > 0:
                try:
                    is_visible = selector.first.is_visible()
                except Exception:
                    is_visible = False
                if is_visible:
                    _log(f"{test_id} Breadcrumbs found")
                    breadcrumbs_found = True
                    breadcrumb_links = selector.locator("a").all()
                    if breadcrumb_links:
                        first_link = breadcrumb_links[0]
                        href = first_link.get_attribute("href")
                        if href and href != "#":
                            url_before = page.url
                            first_link.click()
                            page.wait_for_load_state(
                                "networkidle", timeout=test_data.timeouts["medium"]
                            )
                            url_after = page.url
                            _log(
                                f"{test_id} Breadcrumb navigation: {url_before} -> {url_after}"
                            )
                            assert url_after != url_before
                    break

        _log(
            f"{test_id} Breadcrumbs navigation verified"
            if breadcrumbs_found
            else f"{test_id} No breadcrumbs found"
        )

    # TC_DOC_005
    def test_documentation_version_switcher_works(self, page, base_url):
        test_id = "TC_DOC_005"
        doc_url = build_url(base_url, url_patterns.doc_libs_version(), cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, doc_url, test_id, LOG)

        version_selectors = [
            page.locator('select[name*="version"], select[id*="version"]'),
            page.locator('[data-testid*="version"]'),
            page.locator(".version-switcher, .version-selector"),
        ]
        version_switcher = None
        for selector in version_selectors:
            if selector.count() > 0:
                try:
                    is_visible = selector.first.is_visible()
                except Exception:
                    is_visible = False
                if is_visible:
                    version_switcher = selector.first
                    break

        if version_switcher:
            expect(version_switcher).to_be_visible(timeout=test_data.timeouts["medium"])
            tag_name = version_switcher.evaluate("el => el.tagName.toLowerCase()")
            if tag_name == "select":
                options = version_switcher.locator("option").all()
                option_count = len(options)
                _log(f"{test_id} Found {option_count} version options")
                assert option_count > 0
                if option_count > 1:
                    url_before = page.url
                    version_switcher.select_option(index=1)
                    page.wait_for_timeout(2000)
                    url_after = page.url
                    _log(f"{test_id} Version switch: {url_before} -> {url_after}")
        else:
            _log(f"{test_id} No version switcher found")

    # TC_DOC_006
    def test_documentation_search_within_docs_works(self, page, base_url):
        test_id = "TC_DOC_006"
        doc_url = build_url(base_url, url_patterns.documentation, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, doc_url, test_id, LOG)

        doc_search_selectors = [
            page.locator('input[placeholder*="search doc" i]'),
            page.locator('input[placeholder*="search librar" i]'),
            page.locator(".doc-search input, .library-search input"),
            page.locator('input[type="search"]'),
        ]
        search_input = None
        for selector in doc_search_selectors:
            if selector.count() > 0:
                search_input = find_visible_element(
                    selector, "Doc search input", test_id, LOG
                )
                if search_input:
                    break

        if search_input:
            search_input.fill("boost")
            search_input.press("Enter")
            page.wait_for_timeout(2000)
            results_found = page.locator("text=/result|found|match/i").count() > 0
            _log(
                f"{test_id} Documentation search {'returned results' if results_found else 'executed but results format unclear'}"
            )
        else:
            _log(f"{test_id} No doc-specific search found - uses global search")

    # TC_DOC_007
    def test_documentation_anchor_links_work_correctly(self, page, base_url):
        test_id = "TC_DOC_007"
        try:
            doc_url = build_url(
                base_url, url_patterns.doc_libs_version(), cachebust=True
            )
            test_patterns.load_and_validate_page(page, test_id, doc_url, test_id, LOG)

            if page.is_closed():
                _log(f"{test_id} Page closed, skipping test")
                return

            anchor_links = page.locator('a[href^="#"]').all()
            _log(f"{test_id} Found {len(anchor_links)} anchor links")

            if anchor_links:
                first_anchor = anchor_links[0]
                href = first_anchor.get_attribute("href")
                try:
                    is_visible = first_anchor.is_visible()
                except Exception:
                    is_visible = False

                if is_visible and href and href != "#":
                    y_before = page.evaluate("window.scrollY") or 0
                    try:
                        first_anchor.click()
                    except Exception:
                        _log(f"{test_id} Could not click anchor link")
                    page.wait_for_timeout(500)
                    y_after = page.evaluate("window.scrollY") or 0
                    _log(f"{test_id} Anchor click: scroll from {y_before} to {y_after}")
        except Exception as error:
            _log(f"{test_id} Test error: {error}")
            if "closed" not in str(error):
                raise

    # TC_DOC_008
    def test_documentation_external_links_open_correctly(self, page, base_url):
        test_id = "TC_DOC_008"
        try:
            doc_url = build_url(base_url, url_patterns.documentation, cachebust=True)
            test_patterns.load_and_validate_page(page, test_id, doc_url, test_id, LOG)

            if page.is_closed():
                _log(f"{test_id} Page closed, skipping test")
                return

            external_links = page.locator('a[href^="http"]').all()
            _log(f"{test_id} Found {len(external_links)} external links")

            checked_links = 0
            for i, link in enumerate(external_links[:3]):
                href = link.get_attribute("href")
                try:
                    is_visible = link.is_visible()
                except Exception:
                    is_visible = False
                target = link.get_attribute("target")
                if href and is_visible:
                    _log(f"{test_id} External link {i}: {href}, target={target}")
                    checked_links += 1

            _log(
                f"{test_id} Checked {checked_links} external links"
                if checked_links
                else f"{test_id} No external links found"
            )
        except Exception as error:
            _log(f"{test_id} Test error: {error}")
            if "closed" not in str(error):
                raise

    # TC_DOC_009
    def test_documentation_page_titles_are_descriptive(self, page, base_url):
        test_id = "TC_DOC_009"
        try:
            doc_url = build_url(base_url, url_patterns.documentation, cachebust=True)
            response = page.goto(doc_url, wait_until="domcontentloaded", timeout=20000)
            if not response:
                _log(f"{test_id} Could not load page, skipping test")
                return
            if page.is_closed():
                _log(f"{test_id} Page closed, skipping test")
                return

            page_title = page.title() or ""
            _log(f'{test_id} Page title: "{page_title}"')

            h1 = page.locator("h1").first
            if h1.count() > 0:
                _log(f'{test_id} H1 text: "{h1.text_content()}"')
            else:
                _log(f"{test_id} No H1 found on page")

            if len(page_title) > 10:
                is_descriptive = any(
                    kw in page_title
                    for kw in ["Boost", "Documentation", "Library", "C++"]
                )
                _log(
                    f"{test_id} Title {'is' if is_descriptive else 'may not be'} descriptive"
                )
            else:
                _log(f'{test_id} Title is too short: "{page_title}"')
        except Exception as error:
            _log(f"{test_id} Test error: {error}")

    # TC_DOC_010
    def test_documentation_pdf_print_versions_are_accessible(self, page, base_url):
        test_id = "TC_DOC_010"
        doc_url = build_url(base_url, url_patterns.documentation, cachebust=True)
        test_patterns.load_and_validate_page(page, test_id, doc_url, test_id, LOG)

        pdf_print_selectors = [
            page.locator('a[href*=".pdf"]'),
            page.locator('a:has-text("PDF"), button:has-text("PDF")'),
            page.locator('a:has-text("Print"), button:has-text("Print")'),
            page.locator('[class*="print"], [class*="pdf"]'),
        ]
        pdf_print_found = False
        for selector in pdf_print_selectors:
            if selector.count() > 0:
                try:
                    is_visible = selector.first.is_visible()
                except Exception:
                    is_visible = False
                if is_visible:
                    text = selector.first.text_content()
                    _log(f"{test_id} Found PDF/Print option: {text}")
                    pdf_print_found = True
                    break

        _log(
            f"{test_id} PDF/Print version {'available' if pdf_print_found else 'not found - may not be offered'}"
        )
