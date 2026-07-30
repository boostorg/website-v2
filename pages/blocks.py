from wagtail.blocks import CharBlock
from wagtail.blocks import RichTextBlock
from wagtail.blocks import StreamBlock
from wagtail.blocks import URLBlock
from wagtail.embeds.blocks import EmbedBlock
from wagtailmarkdown.blocks import MarkdownBlock


class PollBlock(StreamBlock):
    poll_choice = CharBlock(max_length=200)


BLOG_BLOCK = ("blog", MarkdownBlock())
NEWS_BLOCK = ("news", MarkdownBlock())
LINK_BLOCK = ("url", URLBlock())
VIDEO_BLOCK = ("video", EmbedBlock(label="Video"))


POST_BLOCKS = [
    ("rich_text", RichTextBlock()),
    BLOG_BLOCK,
    NEWS_BLOCK,
    LINK_BLOCK,
    VIDEO_BLOCK,
    ("poll", PollBlock()),
]
