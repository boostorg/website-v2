from .utils import (
    generate_library_docs_url,
    generate_library_docs_url_v2,
    generate_library_docs_url_v3,
    generate_library_docs_url_v4,
    generate_library_docs_url_bind_v1,
    generate_library_docs_url_bind_v2,
    generate_library_docs_url_math_v1,
    generate_library_docs_url_utility_v1,
    generate_library_docs_url_utility_v2,
    generate_library_docs_url_utility_v3,
    generate_library_docs_url_circular_buffer,
    generate_library_docs_url_core,
    generate_library_docs_url_double_nested_library_htm,
    generate_library_docs_url_double_nested_library_html,
    generate_library_docs_url_algorithm,
    generate_library_docs_url_numeric,
    generate_library_docs_url_numeric_2,
    generate_library_docs_url_string_ref,
    generate_library_docs_url_string_view,
    generate_library_docs_url_utility_anchor,
    generate_library_docs_url_throwexception,
)


# Mapping for exeptions to loading URLs for older docs.
# key: Taken from Library.slug
# value: List of dictionaries with instructions for how to format docs URLs for
# those library-versions
#   - generator: function to use to generate the URL. Required.
#   - min_version: The earliest version that should use that generator. Optional.
#   - max_version: The most recent version that should use that generator. Optional.
#   - alternate_slug: If a slug other than the one in the db should be used to generate
#     the URL
LIBRARY_DOCS_EXCEPTIONS = {
    "any": [
        {
            "generator": generate_library_docs_url_v4,
            "min_version": "boost_1_29_0",
            "max_version": "boost_1_33_0",
        }
    ],
    "call-traits": [
        {
            "generator": generate_library_docs_url_utility_v1,
            "max_version": "boost_1_60_0",
        }
    ],
    "circular-buffer": [
        {
            "generator": generate_library_docs_url_v4,
            "max_version": "boost_1_60_0",
            "min_version": "boost_1_55_0",
        },
        {
            "generator": generate_library_docs_url_circular_buffer,
            "max_version": "boost_1_54_0",
        },
    ],
    "compressed-pair": [
        {
            "generator": generate_library_docs_url_utility_v1,
            "max_version": "boost_1_60_0",
        }
    ],
    "date-time": [
        {
            "generator": generate_library_docs_url_v4,
            "max_version": "boost_1_60_0",
        }
    ],
    "detail": [
        {
            "generator": generate_library_docs_url,
            "min_version": "boost_1_61_0",
        },
    ],
    "dynamic-bitset": [
        {
            "generator": generate_library_docs_url_double_nested_library_html,
            "max_version": "boost_1_60_0",
        }
    ],
    "enable-if": [
        {"generator": generate_library_docs_url_core, "max_version": "boost_1_60_0"}
    ],
    "function-types": [
        {"generator": generate_library_docs_url, "max_version": "boost_1_60_0"}
    ],
    "functionalhash": [
        {
            "generator": generate_library_docs_url_v4,
            "max_version": "boost_1_66_0",
            "alternate_slug": "hash",
        }
    ],
    "functionaloverloaded-function": [
        {
            "generator": generate_library_docs_url,
            "max_version": "boost_1_60_0",
            "alternate_slug": "functional/overloaded_function",
        }
    ],
    "graphparallel": [
        {
            "generator": generate_library_docs_url,
            "max_version": "boost_1_62_0",
            "min_version": "boost_1_40",
            "alternate_slug": "graph_parallel",
        },
    ],
    "identity-type": [
        {
            "generator": generate_library_docs_url_utility_v2,
            "max_version": "boost_1_60_0",
        }
    ],
    "in-place-factory-typed-in-place-factory": [
        {
            "generator": generate_library_docs_url_utility_v3,
            "max_version": "boost_1_60_0",
            "alternate_slug": "in_place_factories",
        }
    ],
    "interprocess": [
        {"generator": generate_library_docs_url_v4, "max_version": "boost_1_47_0"}
    ],
    "interval": [
        {"generator": generate_library_docs_url_numeric, "max_version": "boost_1_47_0"}
    ],
    "intrusive": [
        {"generator": generate_library_docs_url_v4, "max_version": "boost_1_47_0"}
    ],
    "io": [
        {"generator": generate_library_docs_url_v2, "min_version": "boost_1_73_0"},
        {
            "generator": generate_library_docs_url_v3,
            "max_version": "boost_1_72_0",
        },
    ],
    "iterator": [
        {"generator": generate_library_docs_url_v3, "max_version": "boost_1_60_0"},
    ],
    "lexical-cast": [
        {
            "generator": generate_library_docs_url_v4,
            "max_version": "boost_1_60_0",
            "alternate_slug": "boost_lexical_cast",
        }
    ],
    "local-function": [
        {"generator": generate_library_docs_url, "max_version": "boost_1_60_0"}
    ],
    "math-common-factor": [
        {
            "generator": generate_library_docs_url_math_v1,
            "max_version": "boost_1_60_0",
            "alternate_slug": "gcd_lcm",
        }
    ],
    "math-octonion": [
        {
            "generator": generate_library_docs_url_math_v1,
            "max_version": "boost_1_60_0",
            "alternate_slug": "octonions",
        }
    ],
    "math-quaternion": [
        {
            "generator": generate_library_docs_url_math_v1,
            "max_version": "boost_1_60_0",
            "alternate_slug": "quaternions",
        }
    ],
    "mathspecial-functions": [
        {
            "generator": generate_library_docs_url_math_v1,
            "max_version": "boost_1_60_0",
            "alternate_slug": "special",
        }
    ],
    "member-function": [
        {
            "generator": generate_library_docs_url_bind_v1,
            "max_version": "boost_1_60_0",
            "min_version": "boost_1_59_0",
            "alternate_slug": "mem_fn",
        },
        {
            "generator": generate_library_docs_url_bind_v2,
            "max_version": "boost_1_57_0",
            "alternate_slug": "mem_fn",
        },
    ],
    "min-max": [
        {
            "generator": generate_library_docs_url_algorithm,
            "max_version": "boost_1_60_0",
            "alternate_slug": "minmax",
        }
    ],
    "multi-array": [
        {"generator": generate_library_docs_url_v3, "max_version": "boost_1_60_0"},
    ],
    "multi-index": [
        {"generator": generate_library_docs_url_v3, "max_version": "boost_1_60_0"},
    ],
    "numeric-conversion": [
        {
            "generator": generate_library_docs_url_numeric_2,
            "max_version": "boost_1_60_0",
            "alternate_slug": "conversion",
        }
    ],
    "program-options": [
        {"generator": generate_library_docs_url_v4, "max_version": "boost_1_60_0"}
    ],
    "result-of": [
        {
            "generator": generate_library_docs_url_utility_anchor,
            "max_version": "boost_1_60_0",
        }
    ],
    "scope-exit": [
        {"generator": generate_library_docs_url, "max_version": "boost_1_60_0"}
    ],
    "smart-ptr": [
        {
            "generator": generate_library_docs_url_double_nested_library_htm,
            "max_version": "boost_1_60_0",
        }
    ],
    "static-assert": [
        {
            "generator": generate_library_docs_url_double_nested_library_htm,
            "max_version": "boost_1_60_0",
        }
    ],
    "string-algo": [
        {"generator": generate_library_docs_url_v4, "max_version": "boost_1_60_0"}
    ],
    "string-ref": [
        {
            "generator": generate_library_docs_url_string_ref,
            "max_version": "boost_1_77_0",
        }
    ],
    # Still need to deal with the upload changes
    "string-view": [
        {
            "generator": generate_library_docs_url_string_view,
            "max_version": "boost_1_83_0",
        }
    ],
    "throwexception": [
        {
            "generator": generate_library_docs_url_throwexception,
            "max_version": "boost_1_60_0",
            "alternate_slug": "boost_throw_exception_hpp",
        }
    ],
    "type-erasure": [
        {
            "generator": generate_library_docs_url_v4,
            "max_version": "boost_1_60_0",
            "alternate_slug": "boost_typeerasure",
        }
    ],
    "type-index": [
        {
            "generator": generate_library_docs_url_v4,
            "max_version": "boost_1_60_0",
            "alternate_slug": "boost_typeindex",
        }
    ],
    # Not loading before 1.34.0
    "type-traits": [
        {"generator": generate_library_docs_url, "max_version": "boost_1_60_0"}
    ],
    # Missing before 1.60.0
    "winapi": [{"generator": generate_library_docs_url}],
    # Not loading the ones before 1.60.0
    "value-initialized": [
        {
            "generator": generate_library_docs_url_utility_v1,
            "max_version": "boost_1_60_0",
            "alternate_slug": "value_init",
        }
    ],
}


# This constant is for library-version docs that we know are missing
LIBRARY_DOCS_MISSING = {
    # All versions older than this one are missing docs
    "detail": [{"max_version": "boost-1.60.0"}],
    "exception": [{"max_version": "boost-1.35.0"}],
    # All versions between 1.34.0 and 1.39.0, inclusive, are missing
    "graphparallel": [{"min_version": "boost-1.34.0", "max_version": "boost-1.39.0"}],
    "log": [{"max_version": "boost-1.53.0"}],
    "winapi": [{"min_version": "boost-1.56.0", "max_version": "boost-1.60.0"}],
}

# Library-versions that we should not attempt to load at all
SKIP_LIBRARY_VERSIONS = {
    "algorithm": [{"max_version": "boost-1.49.0"}],
    "identity-type": [{"max_version": "boost-1.49.0"}],
}

# List of versions for which we know docs are missing
VERSION_DOCS_MISSING = ["boost-1.33.0"]
