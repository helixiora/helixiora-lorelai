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

from langchain.docstore.document import Document

from .base_processor import BaseProcessor, ProcessorResult, ProcessorStatus
from .config import ProcessorConfig


class PDFProcessor(BaseProcessor):
    """Processor for PDF files using PyPDF2."""

    @classmethod
    def supported_extensions(cls) -> list[str]:
        """Return the supported file extensions.

        Returns
        -------
        list[str]
            List containing '.pdf'
        """
        return [".pdf"]

    @classmethod
    def supported_mimetypes(cls) -> list[str]:
        """Return the supported MIME types.

        Returns
        -------
        list[str]
            List containing 'application/pdf'
        """
        return ["application/pdf"]

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
        start_page = config.get("start_page", 1)
        end_page = config.get("end_page")

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

                extraction_log.append(f"Extracted text from page {i + 1}")

                # Create document with metadata
                doc = Document(
                    page_content=text,
                    metadata={
                        "page": i + 1,
                        "source_type": "pdf",
                        "total_pages": num_pages,
                        "pdf_version": pdf_reader.pdf_version,  # Add PDF-specific metadata
                    },
                )
                documents.append(doc)

            except Exception as e:
                error_msg = f"Error processing page {i + 1}: {str(e)}"
                extraction_log.append(error_msg)
                errors.append(error_msg)
                continue

        return documents, errors

    def process(
        self,
        *,
        file_path: str | None = None,
        file_bytes: bytes | None = None,
        config: ProcessorConfig | None = None,
    ) -> ProcessorResult:
        """Process a PDF file and extract its text.

        Parameters
        ----------
        file_path : str | None, optional
            Path to the PDF file, by default None
        file_bytes : bytes | None, optional
            Raw bytes of the PDF file, by default None
        config : ProcessorConfig | None, optional
            Configuration for processing, by default None

        Returns
        -------
        ProcessorResult
            The result of processing the PDF, including:
            - status (ok or error)
            - message
            - extracted documents (one per page)
            - combined extracted text
            - extraction log

        Raises
        ------
        ValueError
            If neither or both file_path and file_bytes are provided
        """
        extraction_log = []

        # Input validation
        if bool(file_path) == bool(file_bytes):  # both True or both False
            message = "Exactly one of file_path or file_bytes must be provided"
            extraction_log.append(message)
            return ProcessorResult(
                status=ProcessorStatus.ERROR,
                message=message,
                extraction_log=extraction_log,
            )

        # Use default configuration if not provided
        config = config or ProcessorConfig()

        # Apply pre-processing
        input_data = self.pre_process(file_path if file_path else file_bytes)

        # Extract text from the PDF
        documents, errors = self.extract_text(input_data, config, extraction_log)

        # Apply post-processing
        documents = self.post_process(documents)

        # Determine final status and message
        if not documents:
            status = ProcessorStatus.ERROR
            message = "No text could be extracted from the PDF"
        elif errors:
            status = ProcessorStatus.ERROR
            message = f"Completed with {len(errors)} errors"
        else:
            status = ProcessorStatus.OK
            message = "Successfully extracted text from all pages"

        return ProcessorResult(
            status=status,
            message=message,
            documents=documents,
            extracted_text="\n\n".join(extraction_log),
            extraction_log=extraction_log,
        )
