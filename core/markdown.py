import frontmatter
from core.boostrenderer import BoostRenderer
from mistletoe import Document


def process_md(filename):
    with open(filename) as f:
        post = frontmatter.load(f)
        metadata = post.metadata
        content = post.content

        with BoostRenderer() as renderer:
            doc = Document(content)
            rendered = renderer.render(doc)

    return metadata, rendered
