WORDCLOUD_FONT = "NotoSansMono-Regular.ttf"
WEB_ANALYTICS_DOMAIN = "boost.org"
WEB_ANALYTICS_API_URL = (
    f"https://plausible.io/api/stats/{WEB_ANALYTICS_DOMAIN}/top-stats/?period=custom"
    "&from={:%Y-%m-%d}&to={:%Y-%m-%d}"
)
WEB_ANALYTICS_API_URL_V2 = "https://plausible.io/api/v2/query"
WEB_ANALYSTICS_API_TOP_STATS_PAYLOAD = {
    "site_id": "dummy.site",
    "metrics": ["visitors", "pageviews", "bounce_rate"],
    "date_range": "7d",
    "filters": [["is_not", "visit:country_name", [""]]],
    "dimensions": ["visit:country_name", "visit:city_name"],
}
