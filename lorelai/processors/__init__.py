"""Package for document processors that extract text from various file types.

This package provides a flexible and extensible system for extracting and
processing text from various document types. It uses a template pattern to
standardize document processing while allowing for type-specific customization.

For usage instructions and documentation, see:
- Quick start: README.md in this directory
- Detailed guide: /docs/processors.md

Example:
    >>> from lorelai.processors import process_file
    >>> result = process_file(file_path="document.pdf")
    >>> print(result.extracted_text)

Currently supported document types:
- PDF files (using PyPDF2)
"""

from .base_processor import BaseProcessor, ProcessorResult, ProcessorStatus
from .pdf_processor import PDFProcessor
from .config import ProcessorConfig
from .registry import registry, ProcessorRegistry

# Expose the process_file function at package level for convenience
process_file = registry.process_file

__all__ = [
    "BaseProcessor",
    "ProcessorResult",
    "ProcessorStatus",
    "PDFProcessor",
    "ProcessorConfig",
    "ProcessorRegistry",
    "registry",
    "process_file",
]
