import pytest

# The distance layer's tests need its optional dependencies; under a base
# `pip install -e ".[dev]"` this whole directory skips.
pytest.importorskip("pymatgen", reason="distance extra not installed")
pytest.importorskip("ot", reason="distance extra not installed")
pytest.importorskip("pyarrow", reason="distance extra not installed")

from fixtures_distance import diamond_si  # noqa: E402


@pytest.fixture
def diamond():
    return diamond_si()
