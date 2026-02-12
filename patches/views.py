from django.http import FileResponse
from django.views.generic import View
from django.views.generic import TemplateView
from patches.models import LibraryPatch
from versions.models import Version


# Create your views here.
class PatchListView(TemplateView):
    model = LibraryPatch
    template_name = "patches/patch_list_view.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        object_dict = {}
        model = self.model
        for v in Version.objects.all():
            if model_qs := model.objects.filter(library_version__version=v):
                object_dict[v.display_name] = model_qs

        context["grouped_patches"] = object_dict
        return context


class PatchDetailView(View):
    model = LibraryPatch

    def get(self, request, *args, **kwargs):
        model = self.model
        patch_name = kwargs.get("patch_name")
        patch = model.objects.get(patch_name=patch_name)
        return FileResponse(patch.patch_file.open("rb"))
