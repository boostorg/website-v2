# Blocks for use sitewide, or on the Home Page

from wagtail.blocks import (
    StructBlock,
    URLBlock,
    CharBlock,
    PageChooserBlock,
    StructValue,
)


class ButtonValue(StructValue):
    def url(self):
        external_url = self.get("link")
        page = self.get("page")
        return external_url or page.url


class ButtonBlock(StructBlock):
    """
    A block representing a customizable button. Requires a label,
    and may either follow an arbitrary url or link to another page.
    """

    label = CharBlock()
    page = PageChooserBlock(required=False)
    link = URLBlock(required=False)

    class Meta:
        value_class = ButtonValue
