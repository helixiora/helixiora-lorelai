"""PDF processor implementation using PyPDF2.

This module provides a processor for extracting text from PDF files.
It uses PyPDF2 for PDF parsing and text extraction.

For usage instructions and documentation, see:
- Quick start: README.md in this directory
- Detailed guide: /docs/processors.md
- PDF-specific settings: /docs/processors.md#pdf-specific-settings

Example:
    >>> from lorelai.processors import process_file, ProcessorConfig
    >>> config = ProcessorConfig(
    ...     custom_settings={
    ...         "start_page": 1,
    ...         "end_page": 5
    ...     }
    ... )
    >>> result = process_file(file_path="document.pdf", config=config)
"""

from io import BytesIO
import PyPDF2
from typing import final

from langchain.docstore.document import Document

from .base_processor import BaseProcessor
from .config import ProcessorConfig


class PDFProcessor(BaseProcessor):
    """Processor for PDF files using PyPDF2."""

    def __init__(self) -> None:
        """Initialize the PDF processor."""
        super().__init__()

    @classmethod
    @final
    def supported_extensions(cls) -> list[str]:
        """Return the supported file extensions.

        Returns
        -------
        list[str]
            List containing '.pdf'
        """
        return [".pdf"]

    @classmethod
    @final
    def supported_mimetypes(cls) -> list[str]:
        """Return the supported MIME types.

        Returns
        -------
        list[str]
            List containing 'application/pdf'
        """
        return ["application/pdf"]

    @final
    def extract_text(
        self,
        input_data: str | bytes,
        config: ProcessorConfig,
        extraction_log: list[str],
    ) -> tuple[list[Document], list[str]]:
        """Extract text from a PDF file.

        Parameters
        ----------
        input_data : str | bytes
            Either a file path or raw bytes of the PDF
        config : ProcessorConfig
            Configuration for processing
        extraction_log : list[str]
            Log to append extraction messages to

        Returns
        -------
        tuple[list[Document], list[str]]
            A tuple containing:
            - List of extracted documents (one per page)
            - List of error messages (empty if no errors)
        """
        # Load the PDF using PyPDF2
        try:
            if isinstance(input_data, str):
                with open(input_data, "rb") as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    extraction_log.append(f"Loaded PDF from file: {input_data}")
            else:
                pdf_reader = PyPDF2.PdfReader(BytesIO(input_data))
                extraction_log.append("Loaded PDF from bytes input")

            num_pages = len(pdf_reader.pages)
            extraction_log.append(f"PDF has {num_pages} pages")

        except Exception as e:
            return [], [f"Error loading PDF: {str(e)}"]

        # Get page range from config
        custom_settings = config.get("custom_settings", {})
        start_page = custom_settings.get("start_page", 1)
        end_page = custom_settings.get("end_page")

        # Validate and adjust page range
        if end_page and end_page < start_page:
            return [], [
                f"Invalid page range: end page ({end_page}) is before start page ({start_page})"
            ]

        start_idx = start_page - 1  # Convert to 0-based index
        end_idx = min(end_page or num_pages, num_pages)

        documents = []
        errors = []

        # Extract text from each page
        total_pages = end_idx - start_idx
        for i in range(start_idx, end_idx):
            try:
                # Track progress
                self.track_progress(
                    current=i - start_idx + 1,
                    total=total_pages,
                    stage="Extracting text",
                    extraction_log=extraction_log,
                )

                # Extract text
                page = pdf_reader.pages[i]
                text = page.extract_text() or ""

                # Clean the extracted text
                text = self.clean_text(text)

                # Only consider it an error if we couldn't get any text
                if not text.strip():
                    error_msg = f"No text could be extracted from page {i + 1}"
                    extraction_log.append(error_msg)
                    errors.append(error_msg)
                    # Return what we have so far
                    return documents, errors

                extraction_log.append(f"Extracted text from page {i + 1}")

                # Create document with metadata
                doc = Document(
                    page_content=text,
                    metadata={
                        "page": i + 1,
                        "source_type": "pdf",
                        "total_pages": num_pages,
                    },
                )
                documents.append(doc)

            except Exception as e:
                error_msg = f"Error processing page {i + 1}: {str(e)}"
                extraction_log.append(error_msg)
                errors.append(error_msg)
                # Return what we have so far
                return documents, errors

        return documents, errors
