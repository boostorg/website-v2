from ..forms import LibraryForm


def test_library_form_success(tp, library, category):
    form = LibraryForm(data={"categories": [category]})
    assert form.is_valid() is True
