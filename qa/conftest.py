import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--env",
        default="staging",
        choices=["local", "staging", "production"],
        help="Test environment",
    )


@pytest.fixture(scope="session")
def base_url(request):
    env = request.config.getoption("--env")
    urls = {
        "local": "http://localhost:8000",
        "staging": "https://www.stage.boost.org",
        "production": "https://www.boost.org",
    }
    return urls[env]


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": {"width": 1280, "height": 720}}


@pytest.fixture(autouse=True)
def screenshot_on_failure(page, request):
    yield
    if request.node.rep_call.failed if hasattr(request.node, "rep_call") else False:
        import pathlib

        pathlib.Path("screenshots").mkdir(exist_ok=True)
        name = request.node.name.replace(" ", "_")
        page.screenshot(path=f"screenshots/{name}_failure.png", full_page=True)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)
