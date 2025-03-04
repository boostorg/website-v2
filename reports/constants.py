WORDCLOUD_FONT = "notosans_mono.woff"
WEB_ANALYTICS_DOMAIN = "preview.boost.org"
WEB_ANALYTICS_API_URL = (
    f"https://plausible.io/api/stats/{WEB_ANALYTICS_DOMAIN}/top-stats/?period=custom"
    "&from={:%Y-%m-%d}&to={:%Y-%m-%d}"
)
