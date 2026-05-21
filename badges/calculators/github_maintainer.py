from textwrap import dedent

from badges.calculators.base_calculator import BaseCalculator


class GithubMaintainer(BaseCalculator):
    class_reference = "github_maintainer"
    title = "Active Library Maintainer"
    display_name = "Library Maintainer"
    description = dedent(
        """
        Awarded to users who continuously make contributions to the project via GitHub.
        This badge recognizes active participation in the development community.
        """
    ).strip()
    badge_image_light = "github_maintainer_light.svg"
    badge_image_dark = "github_maintainer_dark.svg"
    badge_image_small_light = "github_maintainer_light.svg"
    badge_image_small_dark = "github_maintainer_dark.svg"
    is_nft_enabled = False

    def retrieve_data(self):
        return {}

    def determine_achieved(self, metrics):
        # e.g. has made N contributions in X days to 1+ library
        return True

    def calculate_grade(self, metrics) -> int:
        # e.g. number of libraries on which the user has made N contributions in X days
        return 12
