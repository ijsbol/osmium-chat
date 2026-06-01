import tomllib
from pathlib import Path


def _get_version() -> str:
    """Read the package version from the project's ``pyproject.toml``."""
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with pyproject.open("rb") as f:
        return tomllib.load(f)["project"]["version"]


__version__: str = _get_version()

__all__: tuple[str, ...] = (
    "__version__",
)
