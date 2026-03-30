from django_lookbook.preview import LookbookPreview
from django.template.loader import render_to_string


SAMPLE_BARS = [
    {"label": "1.80.0", "height_px": 45},
    {"label": "1.81.0", "height_px": 62},
    {"label": "1.82.0", "height_px": 78},
    {"label": "1.83.0", "height_px": 55},
    {"label": "1.84.0", "height_px": 90},
    {"label": "1.85.0", "height_px": 40},
    {"label": "1.86.0", "height_px": 72},
    {"label": "1.87.0", "height_px": 85},
    {"label": "1.88.0", "height_px": 60},
    {"label": "1.89.0", "height_px": 95},
]


class StatsInNumbersPreview(LookbookPreview):

    def default_theme(self, **kwargs):
        """
        Stats bar chart card with the default theme.

        Template: `v3/includes/_stats_in_numbers.html`

        | Variable | Required | Description |
        |---|---|---|
        | `heading` | Yes | Section heading |
        | `description` | Yes | Short description below heading |
        | `theme` | No | "default", "yellow", "green", or "teal". Default: "default" |
        | `bars` | Yes | List of dicts with `label` and `height_px` |
        | `primary_cta_label` | Yes | Primary button text |
        | `primary_cta_url` | Yes | Primary button URL |
        | `secondary_cta_label` | No | Secondary button text |
        | `secondary_cta_url` | No | Secondary button URL |
        """
        return render_to_string(
            "v3/includes/_stats_in_numbers.html",
            {
                "heading": "Commits per release",
                "description": "Commit count by Boost release for this library.",
                "bars": SAMPLE_BARS,
                "theme": "default",
                "primary_cta_label": "View library",
                "primary_cta_url": "#",
            },
        )

    def yellow_theme(self, **kwargs):
        """
        Stats bar chart with yellow theme.
        """
        return render_to_string(
            "v3/includes/_stats_in_numbers.html",
            {
                "heading": "Commits per release",
                "description": "Commit count by Boost release for this library.",
                "bars": SAMPLE_BARS,
                "theme": "yellow",
                "primary_cta_label": "View library",
                "primary_cta_url": "#",
            },
        )

    def green_theme(self, **kwargs):
        """
        Stats bar chart with green theme.
        """
        return render_to_string(
            "v3/includes/_stats_in_numbers.html",
            {
                "heading": "Commits per release",
                "description": "Commit count by Boost release for this library.",
                "bars": SAMPLE_BARS,
                "theme": "green",
                "primary_cta_label": "View library",
                "primary_cta_url": "#",
            },
        )

    def teal_theme(self, **kwargs):
        """
        Stats bar chart with teal theme.
        """
        return render_to_string(
            "v3/includes/_stats_in_numbers.html",
            {
                "heading": "Commits per release",
                "description": "Commit count by Boost release for this library.",
                "bars": SAMPLE_BARS,
                "theme": "teal",
                "primary_cta_label": "View library",
                "primary_cta_url": "#",
            },
        )

    def with_secondary_cta(self, **kwargs):
        """
        Stats card with both primary and secondary CTA buttons.
        """
        return render_to_string(
            "v3/includes/_stats_in_numbers.html",
            {
                "heading": "Commits per release",
                "description": "Commit count by Boost release for this library.",
                "bars": SAMPLE_BARS,
                "theme": "default",
                "primary_cta_label": "View library",
                "primary_cta_url": "#",
                "secondary_cta_label": "View all stats",
                "secondary_cta_url": "#",
            },
        )

    def few_bars(self, **kwargs):
        """
        Stats card with only 5 bars, demonstrating flexible chart sizing.
        """
        return render_to_string(
            "v3/includes/_stats_in_numbers.html",
            {
                "heading": "Commits per release",
                "description": "Same data limited to 5 bars.",
                "bars": SAMPLE_BARS[:5],
                "theme": "teal",
                "primary_cta_label": "View library",
                "primary_cta_url": "#",
            },
        )
