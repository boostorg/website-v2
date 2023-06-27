from model_bakery import baker
from ..models import RenderedContent


def test_rendered_content_manager_delete_by_content_type():
    baker.make("core.RenderedContent", content_type="keep")
    baker.make("core.RenderedContent", content_type="clear")

    assert RenderedContent.objects.filter(content_type="keep").exists()
    assert RenderedContent.objects.filter(content_type="clear").exists()

    RenderedContent.objects.delete_by_content_type("clear")

    assert RenderedContent.objects.filter(content_type="keep").exists()
    assert not RenderedContent.objects.filter(content_type="clear").exists()
