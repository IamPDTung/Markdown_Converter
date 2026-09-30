"""mdconv — convert documents to Markdown.

A thin CLI + web wrapper around microsoft/markitdown. All format parsing is
delegated to markitdown; this package only handles batching, uploads and the
user interface.
"""

from .engine import ConversionEngine, ConversionError

__version__ = "0.1.0"
__all__ = ["ConversionEngine", "ConversionError", "__version__"]
