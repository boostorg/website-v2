from pathlib import Path

from django.conf import settings
from django.http import FileResponse
from django.http import HttpResponseNotFound
from django.views.generic import View
from django.views.generic import TemplateView

base_dir = settings.BASE_DIR
PATCHES_PATH = Path(base_dir / "patches" / "files")


# Create your views here.
class PatchListView(TemplateView):
    template_name = "patches/patch_list_view.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        object_dict = {}
        version_folders = [x for x in PATCHES_PATH.iterdir() if x.is_dir()]
        version_folders.sort(reverse=True)
        for v in version_folders:
            version_name = (".").join(v.name.split("_"))
            object_dict[version_name] = sorted(
                [x.name for x in v.iterdir() if x.is_file()]
            )

        context["grouped_patches"] = object_dict
        return context


class PatchDetailView(View):
    def get(self, request, *args, **kwargs):
        patch_name = kwargs.get("patch_name")
        patch_files = [x for x in PATCHES_PATH.glob(f"*/{patch_name}")]
        print(patch_name)
        if len(patch_files) < 1:
            return HttpResponseNotFound()
        patch = patch_files[0]

        return FileResponse(patch.open("rb"))
