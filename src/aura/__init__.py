from importlib import metadata

try:
    __version__ = metadata.version("aura-audit")
except metadata.PackageNotFoundError:
    __version__ = "0.0.0.dev0"

__all__ = ["__version__"]
