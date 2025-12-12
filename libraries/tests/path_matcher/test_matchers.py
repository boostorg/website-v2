from libraries.path_matcher.base_path_matcher import LibsPathMatcher


def test_library_in_path_matcher(library_version):
    import os
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

    test_path = "1_84_0/libs/algorithm/doc/html/index.html"
    matcher = LibsPathMatcher(library_version)
    type = matcher.determine_match(test_path)

    print(f"{type}")
