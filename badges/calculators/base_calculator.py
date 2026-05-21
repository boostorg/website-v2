from abc import ABCMeta, abstractmethod
from typing import Any

from django.contrib.auth import get_user_model
from django.utils.functional import cached_property

User = get_user_model()


class BaseCalculator(metaclass=ABCMeta):
    """Base class for badge calculators.

    Subclasses must define the following class attributes:
        class_reference (str): Unique identifier matching the Badge model's calculator_class_reference field
        title (str): Badge title displayed on hover
        display_name (str): Badge name displayed on user profiles
        description (str | None): Description of what the badge represents
        badge_image_light (str): Path to light mode badge image, relative to static/img/badges/
        badge_image_dark (str): Path to dark mode badge image, relative to static/img/badges/
        badge_image_small_light (str): Path to small light mode badge image, relative to static/img/badges/
        badge_image_small_dark (str): Path to small dark mode badge image, relative to static/img/badges/

    Subclasses must also implement:
        retrieve_data(): Returns data needed to calculate the badge
        determine_achieved(): Returns whether the badge has been achieved
        calculate_grade(): Returns the grade/level for the badge
    """

    class_reference: str = None  # type: ignore[assignment]
    title: str = None  # type: ignore[assignment]
    display_name: str = None  # type: ignore[assignment]
    description: str | None = None
    badge_image_light: str = None  # type: ignore[assignment]
    badge_image_dark: str = None  # type: ignore[assignment]
    badge_image_small_light: str = None  # type: ignore[assignment]
    badge_image_small_dark: str = None  # type: ignore[assignment]
    is_nft_enabled: bool = False  # type: ignore[assignment]

    required_fields = (
        "class_reference",
        "title",
        "display_name",
        "badge_image_light",
        "badge_image_dark",
        "badge_image_small_light",
        "badge_image_small_dark",
    )

    def __init__(self, user: User):
        self.validate()
        self.user = user
        self.data = self.retrieve_data()

    @classmethod
    def validate(cls):
        for field in cls.required_fields:
            if not getattr(cls, field, None):
                msg = f"'{field}' on the {cls.__name__} calculator class is not defined"
                raise NotImplementedError(msg)

    @cached_property
    def achieved(self) -> bool:
        return self.determine_achieved(self.data)

    @cached_property
    def grade(self) -> bool | None:
        return self.calculate_grade(self.data)

    @abstractmethod
    def retrieve_data(self) -> dict[str, Any]:
        """This method returns the data needed to generate the grade"""
        raise NotImplementedError

    @abstractmethod
    def determine_achieved(self, metrics: dict[str, Any]) -> bool:
        """This method signifies that the badge has been achieved"""
        raise NotImplementedError

    @abstractmethod
    def calculate_grade(self, metrics: dict[str, Any]) -> int | None:
        """This method calculators the grade for the user based on passed in metrics"""
        raise NotImplementedError
