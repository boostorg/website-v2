class Selectors:
    @staticmethod
    def mobile_toggle(page):
        return (
            page.locator(
                'button[class*="menu"], button[aria-label*="menu" i], .mobile-toggle, #mobile-toggle, [class*="hamburger"]'
            )
            .or_(page.locator('button[aria-expanded], button[data-toggle="menu"]'))
            .or_(page.locator(".nav-toggle, .navbar-toggle, .menu-toggle"))
        )

    @staticmethod
    def mobile_menu(page):
        return (
            page.locator(
                '[class*="mobile-menu"], [class*="nav-menu"][class*="open"], nav ul[class*="show"], .mobile-nav'
            )
            .or_(
                page.locator(
                    '[aria-expanded="true"] + ul, [aria-expanded="true"] + div'
                )
            )
            .or_(page.locator(".navbar-collapse.show, .nav-menu.active"))
        )

    @staticmethod
    def search_input(page):
        return (
            page.get_by_role("combobox", name="search")
            .or_(
                page.locator(
                    'input[type="search"], input[name="q"], input[placeholder*="search" i]'
                )
            )
            .or_(page.locator('#search-input, .search-input, [class*="search-input"]'))
            .or_(page.locator('[role="searchbox"], [aria-label*="search" i]'))
        )

    # Alias used in some tests
    @staticmethod
    def search(page):
        return Selectors.search_input(page)

    @staticmethod
    def search_trigger(page):
        return (
            page.locator("#gecko-search-button")
            .or_(
                page.locator(
                    'button[aria-label*="search" i], button[title*="search" i]'
                )
            )
            .or_(
                page.locator('.search-trigger, #search-trigger, [class*="search-btn"]')
            )
            .or_(
                page.locator(
                    'button:has-text("Search"), [type="submit"][value*="search" i]'
                )
            )
        )

    @staticmethod
    def logo(page):
        return (
            page.locator('img[src*="Boost_Symbol_Transparent.svg"]')
            .or_(
                page.locator('img[alt*="boost" i], img[title*="boost" i]').filter(
                    has_not=page.locator("iframe")
                )
            )
            .or_(
                page.locator(
                    'img[src*="boost" i][src*="logo" i], img[src*="boost" i][src*="symbol" i]'
                ).filter(has_not=page.locator("iframe"))
            )
            .or_(
                page.locator('.logo img, #logo img, [class*="logo"] img').filter(
                    has_not=page.locator("iframe")
                )
            )
            .or_(page.locator("header img, nav img").first)
            .or_(page.locator('a[href="/"] img, a[href="./"] img').first)
        )

    @staticmethod
    def nav(page):
        return (
            page.get_by_role("navigation")
            .first.or_(page.locator("header nav, .navbar, .navigation"))
            .or_(page.locator('nav, div[class*="nav"], section[class*="nav"]').first)
        )

    @staticmethod
    def nav_links(page):
        return (
            page.get_by_role("navigation")
            .locator("a")
            .or_(page.locator('nav a, header a, [class*="nav"] a'))
            .or_(page.locator(".navbar a, .navigation a"))
        )

    @staticmethod
    def content(page):
        return (
            page.get_by_role("main")
            .or_(page.locator('main, [role="main"], .content, #content'))
            .or_(page.locator(".main-content, .page-content, #main"))
            .or_(page.get_by_role("heading", level=1))
            .or_(page.locator("h1, h2, h3").first)
            .or_(page.locator("article, section").first)
        )

    @staticmethod
    def cta(page):
        return (
            page.get_by_role(
                "link", name="download|release|get started|latest|learn more"
            )
            .or_(
                page.get_by_role(
                    "button", name="download|release|get started|latest|learn more"
                )
            )
            .or_(
                page.locator(
                    'a[href*="download"], a[href*="release"], a[href*="get-started"]'
                )
            )
            .or_(
                page.locator(
                    '.cta, #cta, [class*="cta"], [class*="download"], [class*="release"]'
                )
            )
        )

    @staticmethod
    def external_links(page):
        return (
            page.locator('a[href^="http"]')
            .filter(has_text=".")
            .or_(page.locator('a[target="_blank"]').filter(has_text="."))
        )

    @staticmethod
    def footer(page):
        return (
            page.get_by_role("contentinfo")
            .first.or_(page.locator("footer, .footer, #footer"))
            .or_(page.locator('[role="contentinfo"]'))
        )

    @staticmethod
    def download_links(page):
        return (
            page.locator('a[href*="archives.boost.io"]')
            .or_(page.locator('a[href*="boost_1_85_0"], a[href*="boost-1.85.0"]'))
            .or_(page.locator('a[href$=".tar.gz"], a[href$=".zip"], a[href$=".exe"]'))
            .or_(
                page.locator(
                    'a:has-text("Download"), a:has-text("tar.gz"), a:has-text("zip")'
                )
            )
            .or_(page.locator('[class*="download"], #download'))
        )


selectors = Selectors()
