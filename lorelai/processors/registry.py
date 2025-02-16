"""Registry for document processors that handles processor selection and file processing.

This module provides a central registry for document processors and handles
automatic processor selection based on file type or MIME type.

For usage instructions and documentation, see:
- Quick start: README.md in this directory
- Detailed guide: /docs/processors.md
- Registry architecture: /docs/processors.md#registry

Example:
    >>> from lorelai.processors import registry
    >>> # Process a file (automatically selects appropriate processor)
    >>> result = registry.process_file(file_path="document.pdf")
    >>>
    >>> # Register a custom processor
    >>> registry.register_processor(MyCustomProcessor)
"""

import os
import mimetypes
from pydantic import BaseModel

from .base_processor import BaseProcessor, ProcessorResult
from .pdf_processor import PDFProcessor


class ProcessorRegistry:
    """Registry that manages document processors and handles file processing.

    This class maintains a mapping of file extensions and MIME types to their
    appropriate processors, and provides a simple interface to process files
    without needing to know which processor to use.
    """

    def __init__(self):
        """Initialize the registry with available processors."""
        self._processors: dict[str, type[BaseProcessor]] = {}
        self._mime_processors: dict[str, type[BaseProcessor]] = {}

        # Register built-in processors
        self.register_processor(PDFProcessor)

    def register_processor(self, processor_class: type[BaseProcessor]) -> None:
        """Register a new processor.

        Parameters
        ----------
        processor_class : Type[BaseProcessor]
            The processor class to register.
        """
        # Register file extensions
        for ext in processor_class.supported_extensions():
            self._processors[ext.lower()] = processor_class

        # Register MIME types
        for mime in processor_class.supported_mimetypes():
            self._mime_processors[mime.lower()] = processor_class

    def get_processor_for_file(
        self,
        file_path: str | None = None,
        mime_type: str | None = None,
    ) -> type[BaseProcessor] | None:
        """Get the appropriate processor for a file.

        Parameters
        ----------
        file_path : Optional[str], optional
            Path to the file, by default None
        mime_type : Optional[str], optional
            MIME type of the file, by default None

        Returns
        -------
        Optional[Type[BaseProcessor]]
            The processor class if found, None otherwise.
        """
        if file_path:
            # Try to get processor by file extension
            ext = os.path.splitext(file_path)[1].lower()
            if ext in self._processors:
                return self._processors[ext]

            # If no processor found by extension, try MIME type
            if not mime_type:
                mime_type = mimetypes.guess_type(file_path)[0]

        if mime_type:
            # Try to get processor by MIME type
            return self._mime_processors.get(mime_type.lower())

        return None

    def process_file(
        self,
        *,
        file_path: str | None = None,
        file_bytes: bytes | None = None,
        mime_type: str | None = None,
        config: BaseModel | None = None,
    ) -> ProcessorResult:
        """Process a file using the appropriate processor.

        This method automatically selects the appropriate processor based on
        the file extension or MIME type and processes the file.

        Parameters
        ----------
        file_path : Optional[str], optional
            Path to the file to process, by default None
        file_bytes : Optional[bytes], optional
            Raw bytes of the file to process, by default None
        mime_type : Optional[str], optional
            MIME type of the file, by default None
        config : Optional[BaseModel], optional
            Configuration for the processor, by default None

        Returns
        -------
        ProcessorResult
            The result of processing the file.

        Raises
        ------
        ValueError
            If no suitable processor is found or if the input is invalid.
        """
        # Input validation
        if bool(file_path) == bool(file_bytes):
            raise ValueError("Exactly one of file_path or file_bytes must be provided")

        # Get the appropriate processor
        processor_class = self.get_processor_for_file(
            file_path=file_path,
            mime_type=mime_type,
        )
        if not processor_class:
            supported_types = list(self._processors.keys()) + list(self._mime_processors.keys())
            raise ValueError(
                f"No processor found for the given file type. Supported types: {supported_types}"
            )

        # Create processor instance and process the file
        processor = processor_class()
        return processor.process(
            file_path=file_path,
            file_bytes=file_bytes,
            config=config,
        )


# Create a global registry instance
registry = ProcessorRegistry()
