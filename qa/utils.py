import pathlib
import time


def _log(message, log_file="test-logs.txt"):
    with open(log_file, "a") as f:
        f.write(message + "\n")


def log_and_screenshot(page, test_name, message, path, log_file="test-logs.txt"):
    _log(f"{test_name}: {message}", log_file)
    if not page.is_closed():
        try:
            pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=path, full_page=True, timeout=3000)
            _log(f"Screenshot saved: {path}", log_file)
        except Exception as err:
            _log(f"Screenshot failed: {err}", log_file)
    else:
        _log("Screenshot skipped: Page is closed", log_file)


def safe_goto(page, test_name, url, wait_until="networkidle", log_file="test-logs.txt"):
    max_retries = 3
    final_url = url
    for attempt in range(1, max_retries + 1):
        if page.is_closed():
            _log(
                f"{test_name} Page is closed before goto attempt {attempt} for {url}",
                log_file,
            )
            return {"success": False, "final_url": final_url}
        try:
            response = page.goto(final_url, wait_until=wait_until, timeout=20000)
            status = response.status if response else "no response"
            redirect_url = None
            if response and 300 <= (response.status or 0) < 400:
                redirect_url = response.header_value("location")
            _log(
                f"{test_name} Navigated to {final_url} with status {status}"
                + (f", Redirect: {redirect_url}" if redirect_url else "")
                + f" on attempt {attempt}",
                log_file,
            )
            if redirect_url and redirect_url != final_url:
                if redirect_url.startswith("/"):
                    from urllib.parse import urlparse

                    parsed = urlparse(page.url)
                    final_url = f"{parsed.scheme}://{parsed.netloc}{redirect_url}"
                else:
                    final_url = redirect_url
                continue
            return {"success": True, "final_url": final_url}
        except Exception as err:
            _log(
                f"{test_name} Goto attempt {attempt} failed for {final_url}: {err}",
                log_file,
            )
            if attempt == max_retries:
                return {"success": False, "final_url": final_url}
            time.sleep(1)
    return {"success": False, "final_url": final_url}
