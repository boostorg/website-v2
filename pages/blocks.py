from wagtail.blocks import CharBlock
from wagtail.blocks import RichTextBlock
from wagtail.blocks import StructBlock
from wagtail.blocks import StreamBlock
from wagtail.blocks import URLBlock
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images.blocks import ImageChooserBlock
from wagtailmarkdown.blocks import MarkdownBlock


class CustomVideoBlock(StructBlock):
    video = EmbedBlock()
    thumbnail = ImageChooserBlock()


class PollBlock(StreamBlock):
    poll_choice = CharBlock(max_length=200)


POST_BLOCKS = [
    ("rich_text", RichTextBlock()),
    ("markdown", MarkdownBlock()),
    ("url", URLBlock()),
    ("video", CustomVideoBlock(label="Video")),
    ("poll", PollBlock()),
]
