# Blocks for use sitewide, or on the Home Page

from wagtail.blocks import StructBlock, URLBlock, CharBlock, PageChooserBlock


class ButtonBlock(StructBlock):
    """
    A block representing a customizable button. Requires a label,
    and may either follow an arbitrary url or link to another page.
    """

    label = CharBlock()
    page = PageChooserBlock(required=False)
    link = URLBlock(required=False)
