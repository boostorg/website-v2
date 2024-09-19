def generate_library_docs_url(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    General use
    """
    return f"/doc/libs/{boost_url_slug}/libs/{library_slug}/doc/html/index.html"


def generate_library_docs_url_v2(boost_url_slug, library_slug):
    """ "Generate a documentation url with a specific format

    For use primarily with IO, versions 1.73.0 and up
    """
    new_boost_url_slug = boost_url_slug.replace("boost_", "")
    return f"/doc/libs/{new_boost_url_slug}/libs/{library_slug}/doc/html/{library_slug}.html"  # noqa


def generate_library_docs_url_v3(boost_url_slug, library_slug):
    """ "Generate a documentation url with a specific format

    For use primarily with IO, versions 1.64.0-1.72.
    """
    return f"/doc/libs/{boost_url_slug}/libs/{library_slug}/doc/index.html"


def generate_library_docs_url_v4(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    First used for Any, versions 1.33.0 and older
    """
    return f"/doc/libs/{boost_url_slug}/doc/html/{library_slug}.html"


def generate_library_docs_url_bind_v1(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    First used for Member Function, versions 1.60.0 and older
    """
    return f"/doc/libs/{boost_url_slug}/libs/bind/doc/html/{library_slug}.html"


def generate_library_docs_url_bind_v2(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    First used for Member Function, versions 1.60.0 and older
    """
    return f"/doc/libs/{boost_url_slug}/libs/bind/{library_slug}.html"


def generate_library_docs_url_math_v1(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    First used for Math Common Factor, versions 1.60.0 and older
    """
    return f"/doc/libs/{boost_url_slug}/libs/math/doc/html/{library_slug}.html"


def generate_library_docs_url_utility_v1(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    First used for Call Traits, versions 1.60.0 and below.
    """
    return f"/doc/libs/{boost_url_slug}/libs/utility/{library_slug}.htm"


def generate_library_docs_url_utility_v2(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    First used for Identity Types, version 1.60.0 and below.
    """
    return f"/doc/libs/{boost_url_slug}/libs/utility/{library_slug}/doc/html/index.html"


def generate_library_docs_url_utility_v3(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    Same as v1, but .html and not .htm

    First used for In Place Factories, version 1.60.0 and below.
    """
    return f"/doc/libs/{boost_url_slug}/libs/utility/{library_slug}.html"


def generate_library_docs_url_circular_buffer(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    First used with Circular Buffer v. 1.54.0 and before"""
    return f"/doc/libs/{boost_url_slug}/libs/{library_slug}/doc/{library_slug}.html"


def generate_library_docs_url_core(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    First used for Enable If, versions 1.60.0 and below.
    """
    return f"/doc/libs/{boost_url_slug}/libs/core/doc/html/core/{library_slug}.html"


def generate_library_docs_url_double_nested_library_html(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    First used for Dynamic Bitset, versions 1.60.0 and below.
    """
    return f"/doc/libs/{boost_url_slug}/libs/{library_slug}/{library_slug}.html"


def generate_library_docs_url_double_nested_library_htm(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    Ends in .htm, not .html

    First used for Dynamic Bitset, versions 1.60.0 and below.
    """
    return f"/doc/libs/{boost_url_slug}/libs/{library_slug}/{library_slug}.htm"


def generate_library_docs_url_algorithm(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    First used with Min Max, versions 1.60.0 and below"""
    return f"/doc/libs/{boost_url_slug}/libs/algorithm/{library_slug}/index.html"


def generate_library_docs_url_numeric(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    First used with Interval, versions 1.60.0 and below"""
    return (
        f"/doc/libs/{boost_url_slug}/libs/numeric/{library_slug}/doc/{library_slug}.htm"
    )


def generate_library_docs_url_numeric_2(boost_url_slug, library_slug):
    """Generate a documentation url with a specific format

    First used with Interval, versions 1.60.0 and below"""
    return f"/doc/libs/{boost_url_slug}/libs/numeric/{library_slug}/doc/html/index.html"


def generate_library_docs_url_string_ref(boost_url_slug, library_slug):
    """Generate a documentation URL for the string-ref library-versions"""
    return f"/doc/libs/{boost_url_slug}/libs/utility/doc/html/{library_slug}.html"


def generate_library_docs_url_string_view(boost_url_slug, library_slug):
    """Generate a documentation URL for the string-view library-versions"""
    return f"/doc/libs/{boost_url_slug}/libs/utility/doc/html/utility/utilities/{library_slug}.html"  # noqa


def generate_library_docs_url_throwexception(boost_url_slug, library_slug):
    """Generate a documentation URL for the string-view library-versions"""
    return f"/doc/libs/{boost_url_slug}/libs/exception/doc/{library_slug}.html"


def generate_library_docs_url_utility_anchor(boost_url_slug, library_slug):
    """Generate a documentation URL for a URL that uses an anchor"""
    return f"/doc/libs/{boost_url_slug}/libs/utility/utility.htm#{library_slug}"
