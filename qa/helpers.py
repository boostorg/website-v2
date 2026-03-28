import re
import time
from playwright.sync_api import expect
from utils import log_and_screenshot, safe_goto
from config_helper import test_data


def find_visible_element(locator, element_name, test_id, log_file="test-logs.txt"):
    count = locator.count()
    with open(log_file, "a") as f:
        f.write(f"{test_id} {element_name} locator matched {count} elements\n")
    for i in range(count):
        element = locator.nth(i)
        try:
            is_visible = element.is_visible()
        except Exception:
            is_visible = False
        with open(log_file, "a") as f:
            f.write(f"{test_id} {element_name} {i} visible: {is_visible}\n")
        if is_visible:
            return element
    return None


def check_element_visibility(
    page,
    test_name,
    primary_locator,
    fallback_locators,
    element_name,
    test_id,
    log_file="test-logs.txt",
):
    primary_element = find_visible_element(
        primary_locator, f"{element_name} (primary)", test_id, log_file
    )
    if primary_element:
        expect(primary_element).to_be_visible(timeout=test_data.timeouts["medium"])
        return primary_element

    for i, fallback in enumerate(fallback_locators):
        fallback_element = find_visible_element(
            fallback, f"{element_name} (fallback {i})", test_id, log_file
        )
        if fallback_element:
            with open(log_file, "a") as f:
                f.write(f"{test_id} Using {element_name} fallback {i}\n")
            expect(fallback_element).to_be_visible(timeout=test_data.timeouts["medium"])
            return fallback_element

    log_and_screenshot(
        page,
        test_name,
        f"{element_name} not visible",
        f"screenshots/{test_id.lower()}_{element_name.lower().replace(' ', '_')}_not_visible.png",
        log_file,
    )
    raise AssertionError(f"{element_name} not visible")


def handle_mobile_menu(page, selectors, test_id, log_file="test-logs.txt"):
    mobile_toggle = selectors.mobile_toggle(page)
    count = mobile_toggle.count()
    if count > 0:
        try:
            is_visible = mobile_toggle.first.is_visible()
        except Exception:
            is_visible = False
        with open(log_file, "a") as f:
            f.write(f"{test_id} Mobile toggle visible: {is_visible}\n")
        if is_visible:
            try:
                mobile_toggle.first.click()
                page.wait_for_timeout(500)
                with open(log_file, "a") as f:
                    f.write(f"{test_id} Mobile menu opened\n")
                mobile_menu = selectors.mobile_menu(page)
                try:
                    menu_visible = mobile_menu.is_visible()
                except Exception:
                    menu_visible = False
                if menu_visible:
                    expect(mobile_menu).to_be_visible(
                        timeout=test_data.timeouts["short"]
                    )
            except Exception as error:
                with open(log_file, "a") as f:
                    f.write(f"{test_id} Mobile menu interaction failed: {error}\n")


def perform_search(
    page, test_name, selectors, search_term, test_id, log_file="test-logs.txt"
):
    search_trigger = find_visible_element(
        selectors.search_trigger(page), "Search trigger", test_id, log_file
    )
    if not search_trigger:
        raise AssertionError("Search trigger not found")

    search_trigger.click()
    with open(log_file, "a") as f:
        f.write(f"{test_id} Search trigger clicked\n")

    search_input = selectors.search_input(page)
    count = search_input.count()
    with open(log_file, "a") as f:
        f.write(f"{test_id} Found {count} search input elements\n")

    actual_search_input = None
    for i in range(count):
        element = search_input.nth(i)
        try:
            tag_name = element.evaluate("el => el.tagName.toLowerCase()")
            input_type = element.get_attribute("type") or ""
            role = element.get_attribute("role") or ""
        except Exception:
            continue
        if (
            tag_name == "input"
            and input_type in ("text", "search", "", "combobox")
            or role == "combobox"
        ):
            actual_search_input = element
            with open(log_file, "a") as f:
                f.write(
                    f"{test_id} Using search input element {i} ({tag_name}, type: {input_type}, role: {role})\n"
                )
            break

    if not actual_search_input:
        fallback = page.locator('input[role="combobox"][placeholder*="Search"]').first
        if fallback.count() > 0:
            actual_search_input = fallback
            with open(log_file, "a") as f:
                f.write(f"{test_id} Using fallback search input selector\n")
        else:
            actual_search_input = search_input.first
            with open(log_file, "a") as f:
                f.write(f"{test_id} Using first search element as last resort\n")

    expect(actual_search_input).to_be_visible(timeout=test_data.timeouts["medium"])
    actual_search_input.fill(search_term)
    actual_search_input.press("Enter")
    with open(log_file, "a") as f:
        f.write(f"{test_id} Search performed for: {search_term}\n")
    page.wait_for_timeout(2000)


def find_search_results(page, search_term, test_id, log_file="test-logs.txt"):
    result_selectors = [
        '[class*="search-result"], [class*="result"]',
        '[data-testid*="search"], [data-testid*="result"]',
        ".algolia-autocomplete .aa-dropdown-menu .aa-suggestion",
        '[role="listbox"] [role="option"]',
        ".search-hits, .search-results, #search-results",
    ]
    for selector in result_selectors:
        elements = page.locator(selector)
        count = elements.count()
        with open(log_file, "a") as f:
            f.write(f"{test_id} Found {count} elements with selector: {selector}\n")
        if count > 0:
            return {"element": elements.first, "count": count}

    content_results = page.locator("h1, h2, h3, p, div, span, li").filter(
        has_text=re.compile(search_term, re.I)
    )
    content_count = content_results.count()
    with open(log_file, "a") as f:
        f.write(
            f'{test_id} Found {content_count} content elements containing "{search_term}"\n'
        )
    if content_count > 0:
        return {"element": content_results.first, "count": content_count}

    broad_results = page.get_by_text(re.compile(search_term, re.I))
    broad_count = broad_results.count()
    with open(log_file, "a") as f:
        f.write(f"{test_id} Broad text search found {broad_count} matches\n")
    return {
        "element": broad_results.first if broad_count > 0 else None,
        "count": broad_count,
    }


def check_navigation_link(
    page, test_name, link, index, test_id, home_url, log_file="test-logs.txt"
):
    try:
        href = link.get_attribute("href")
        text = link.text_content() or "unknown"
    except Exception:
        return

    if not href or href == "#" or re.match(r"^https?://", href):
        with open(log_file, "a") as f:
            f.write(
                f'{test_id} Skipping invalid nav link {index}: text="{text}", href="{href}"\n'
            )
        return

    try:
        expect(link).to_be_visible(timeout=test_data.timeouts["short"])
        link.click()
        escaped = re.escape(href)
        expect(page).to_have_url(
            re.compile(escaped), timeout=test_data.timeouts["short"]
        )
        with open(log_file, "a") as f:
            f.write(f'{test_id} Nav link {index} successful: "{text}" -> {href}\n')
        safe_goto(
            page, test_name, home_url, wait_until="domcontentloaded", log_file=log_file
        )
    except Exception as error:
        with open(log_file, "a") as f:
            f.write(
                f'{test_id} Nav link {index} failed: text="{text}", href="{href}", error="{error}"\n'
            )
        log_and_screenshot(
            page,
            test_name,
            f"Navigation failed for link {index}",
            f"screenshots/{test_id.lower()}_link_{index}_failed.png",
            log_file,
        )


def validate_element_details(element, element_name, test_id, log_file="test-logs.txt"):
    details = {}
    for attr, method in [
        ("text", lambda: element.text_content()),
        ("href", lambda: element.get_attribute("href")),
        ("class", lambda: element.get_attribute("class")),
        ("id", lambda: element.get_attribute("id")),
        ("is_visible", lambda: element.is_visible()),
    ]:
        try:
            details[attr] = method()
        except Exception:
            details[attr] = None
    with open(log_file, "a") as f:
        f.write(f"{test_id} {element_name} details: {details}\n")
    return details


class TestPatterns:
    @staticmethod
    def load_and_validate_page(page, test_name, url, test_id, log_file="test-logs.txt"):
        start_time = time.time()
        result = safe_goto(
            page, test_name, url, wait_until="domcontentloaded", log_file=log_file
        )
        if not result["success"]:
            log_and_screenshot(
                page,
                test_name,
                f"Page load failed: {result['final_url']}",
                f"screenshots/{test_id.lower()}_load_failed.png",
                log_file,
            )
            raise AssertionError(f"Page load failed: {result['final_url']}")
        load_time = int((time.time() - start_time) * 1000)
        log_and_screenshot(
            page,
            test_name,
            f"Page loaded in {load_time}ms, URL: {page.url}",
            f"screenshots/{test_id.lower()}_loaded.png",
            log_file,
        )
        return {"load_time": load_time, "final_url": result["final_url"]}

    @staticmethod
    def set_viewport(page, viewport, test_id, log_file="test-logs.txt"):
        page.set_viewport_size(viewport)
        with open(log_file, "a") as f:
            f.write(
                f"{test_id} Viewport set to {viewport['width']}x{viewport['height']}\n"
            )


test_patterns = TestPatterns()
