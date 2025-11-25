from textwrap import dedent

from badges.calculators.base_calculator import BaseCalculator


class LibraryCreator(BaseCalculator):
    class_reference = "library_creator"
    title = "Library Creator"
    display_name = "Library Creator"
    description = dedent(
        """
        Awarded to users who have created and published libraries. This badge recognizes
        contributions to the C++ ecosystem through library development.
        """
    ).strip()
    badge_image_light = "library_creator_light.svg"
    badge_image_dark = "library_creator_dark.svg"
    badge_image_small_light = "library_creator_light.svg"
    badge_image_small_dark = "library_creator_dark.svg"
    is_nft_enabled = True

    def retrieve_data(self):
        return {}

    def determine_achieved(self, metrics):
        # e.g. has created >1 libraries
        return True

    def calculate_grade(self, metrics) -> int:
        # e.g. number of libraries created by the user
        return 1
