import re
from enum import Enum


class SourceDocType(Enum):
    ASCIIDOC = "asciidoc"
    ANTORA = "antora"


SLACK_URL = "https://cpplang.slack.com"
STATIC_CONTENT_EARLY_EXIT_PATH_PREFIXES = ("releases/",)
# possible library versions are: boost_1_53_0_beta1, 1_82_0, 1_55_0b1
BOOST_LIB_PATH_RE = re.compile(r"^(boost_){0,1}([0-9_]*[0-9]+[^/]*)/(.*)")
NO_PROCESS_LIBS = [
    # Do nothing with these - just render contents directly
    "libs/filesystem",
    "libs/gil",
    "libs/hana",
    "libs/locale",
    "libs/iostreams",
    "libs/preprocessor",
    "libs/serialization",
    "libs/wave",
]
NO_WRAPPER_LIBS = [
    # Add a header to these, but no wrapper.
    "libs/array",
    "libs/assert",
    "libs/bloom",
    "libs/charconv",
    "libs/cobalt",
    "libs/compat",
    "libs/container_hash",
    "libs/describe",
    "libs/endian",
    "libs/exception",
    "libs/hash2",
    "libs/io",
    "libs/lambda2",
    "libs/leaf",
    "libs/mp11",
    "libs/predef",
    "libs/process",
    "doc/html/process",
    "libs/property_map_parallel",
    "libs/qvm",
    "libs/redis",
    "libs/smart_ptr",
    "libs/system",
    "libs/throw_exception",
    "libs/unordered",
    "libs/uuid",
    "libs/variant2",
]
FULLY_MODERNIZED_LIB_VERSIONS = [
    # FIXME: we should have a way to opt-in via a flag on the library/lib-version.
    #  Hard-coding these here as a quick fix for now.
    # TODO: create a ticket for this
    "tools/",  # Not a library version, but tools are somewhat analogous
    "1_87_0/libs/charconv",
    "1_88_0/libs/charconv",
    "1_89_0/libs/charconv",
    "latest/libs/charconv",
    "develop/libs/charconv",
    "master/libs/charconv",
    "1_89_0/libs/redis",
    "latest/libs/redis",
    "develop/libs/redis",
    "master/libs/redis",
    "doc/antora/url",
]
RENDERED_CONTENT_BATCH_DELETE_SIZE = 10000
