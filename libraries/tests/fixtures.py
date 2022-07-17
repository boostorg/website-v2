import pytest
from model_bakery import baker


@pytest.fixture
def library(db):
    return baker.make(
        "libraries.Library",
        name="multi_array",
        description="Boost.MultiArray provides a generic N-dimensional array concept definition and common implementations of that interface.",
        github_url="https://github.com/boostorg/multi_array",
    )
