WORDCLOUD_FONT = "NotoSansMono-Regular.ttf"
WEB_ANALYTICS_DOMAIN = "boost.org"
WEB_ANALYTICS_API_URL = (
    f"https://plausible.io/api/stats/{WEB_ANALYTICS_DOMAIN}/top-stats/?period=custom"
    "&from={:%Y-%m-%d}&to={:%Y-%m-%d}"
)
WEB_ANALYTICS_API_URL_V2 = "https://plausible.io/api/v2/query"
WEB_ANALYSTICS_API_TOP_STATS_PAYLOAD = {
    "site_id": WEB_ANALYTICS_DOMAIN,
    "metrics": [
        "visitors",
        "pageviews",
        "bounce_rate",
        "visit_duration",
        "views_per_visit",
        "visits",
    ],
}
WEB_ANALYTICS_CODENAME_MAPPING = {
    "visitors": "Unique Visitors",
    "pageviews": "Total Page pageviews",
    "bounce_rate": "Bounce Rate",
    "visit_duration": "Visit Duration",
    "views_per_visit": "Views per visit",
    "visits": "Total visits",
}
