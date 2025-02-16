"""Base class for document processors that extract text from various file types.

This module provides the base functionality for all document processors.
It implements a template pattern for standardized document processing
while allowing for type-specific customization.

For usage instructions and documentation, see:
- Quick start: README.md in this directory
- Detailed guide: /docs/processors.md

Example:
    >>> from lorelai.processors import process_file
    >>> result = process_file(file_path="document.pdf")
    >>> print(result.extracted_text)
"""

from abc import ABC, abstractmethod
import unicodedata
import hashlib
from datetime import datetime
import re
import logging
import psutil
import os
from enum import Enum
from pydantic import BaseModel
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from typing import Final, TypeAlias, Any, final
import time
import functools

from .config import ProcessorConfig

# Configure logging
logger = logging.getLogger(__name__)


def get_memory_usage():
    """Get current memory usage of the process."""
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / 1024 / 1024  # Convert to MB
    return mem


def log_memory(message: str):
    """Log memory usage with a custom message."""
    mem = get_memory_usage()
    logger.debug("Memory Usage (%s): %.2f MB", message, mem)


def log_time(func):
    """Log the execution time of a function (decorator)."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        logger.debug("Starting %s...", func.__name__)
        result = func(*args, **kwargs)
        end_time = time.time()
        duration = end_time - start_time
        logger.debug(
            "%s completed in %.2f seconds %s",
            func.__name__,
            duration,
            "🟢" if duration < 1 else "🟡" if duration < 5 else "🔴",
        )
        return result

    return wrapper


class ProcessorStatus(str, Enum):
    """Status of a processor's execution."""

    OK = "ok"
    ERROR = "error"
    PARTIAL = "partial"  # Some documents processed, some failed


class ProcessorResult(BaseModel):
    """Result of a processor's execution."""

    status: ProcessorStatus
    message: str | None = None
    documents: list[Document] = []
    extracted_text: str | None = None
    extraction_log: list[str] = []
    processing_stats: dict = {}  # Add processing statistics


# Type aliases for clarity
InputData: TypeAlias = str | bytes
ProcessorError: TypeAlias = tuple[ProcessorResult | None, str | bytes | None]


class BaseProcessor(ABC):
    """Base class for all document processors.

    A processor is responsible for extracting text from a specific type of file
    (e.g., PDF, Word, etc.) and returning it in a standardized format.
    """

    # Common configuration defaults as Final constants
    MIN_CONTENT_LENGTH: Final[int] = 10  # Minimum characters for valid content
    MAX_CONTENT_LENGTH: Final[int] = 1_000_000  # Maximum characters to process
    GARBAGE_RATIO_THRESHOLD: Final[float] = 0.3  # Maximum ratio of garbage characters

    def __init__(self) -> None:
        """Initialize the processor."""
        self._initialized = False
        self._supported_extensions = self.supported_extensions()
        self._supported_mimetypes = self.supported_mimetypes()
        self._initialized = True

    @final
    def __setattr__(self, name: str, value: Any) -> None:
        """Prevent modification of supported formats after initialization."""
        if (
            hasattr(self, "_initialized")
            and self._initialized
            and name in ("_supported_extensions", "_supported_mimetypes")
        ):
            raise AttributeError(f"Cannot modify {name} after initialization")
        super().__setattr__(name, value)

    def _validate_document(self, doc: Document) -> None:
        """Validate a document's structure and content.

        Raises
        ------
        ValueError
            If the document is invalid
        """
        if not isinstance(doc, Document):
            raise ValueError("Document must be an instance of langchain.docstore.document.Document")
        if not doc.page_content:
            raise ValueError("Document must have page content")
        if not isinstance(doc.metadata, dict):
            raise ValueError("Document metadata must be a dictionary")

    def _validate_config(self, config: ProcessorConfig) -> None:
        """Validate processor configuration.

        Raises
        ------
        ValueError
            If the configuration is invalid
        """
        if not isinstance(config, ProcessorConfig):
            raise ValueError("Config must be an instance of ProcessorConfig")

        # Get settings
        chunk_size = config.chunk_size
        if not isinstance(chunk_size, int) or chunk_size <= 0:
            raise ValueError("chunk_size must be a positive integer")

        overlap = config.overlap
        if not isinstance(overlap, int) or overlap < 0:
            raise ValueError("overlap must be a non-negative integer")

        if overlap >= chunk_size:
            raise ValueError("overlap must be less than chunk_size")

        max_chunks = config.max_chunks
        if max_chunks is not None and (not isinstance(max_chunks, int) or max_chunks <= 0):
            raise ValueError("max_chunks must be a positive integer or None")

    @classmethod
    @abstractmethod
    def supported_extensions(cls) -> list[str]:
        """Return the supported file extensions (e.g. ['.pdf']).

        Returns
        -------
        list[str]
            List of file extensions this processor supports (including the dot).
        """
        return []

    @classmethod
    @abstractmethod
    def supported_mimetypes(cls) -> list[str]:
        """Return the supported MIME types (e.g. ['application/pdf']).

        Returns
        -------
        list[str]
            List of MIME types this processor supports.
        """
        return []

    def clean_text(self, text: str) -> str:
        """Clean and normalize extracted text.

        Parameters
        ----------
        text : str
            Raw extracted text

        Returns
        -------
        str
            Cleaned and normalized text
        """
        if not text:
            return text

        # Normalize Unicode characters
        text = unicodedata.normalize("NFKC", text)

        # Remove control characters except newlines and tabs
        text = "".join(
            char
            for char in text
            if char == "\n" or char == "\t" or not unicodedata.category(char).startswith("C")
        )

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\n\s*\n", "\n\n", text)

        # Remove leading/trailing whitespace
        text = text.strip()

        return text

    @final
    @log_time
    def validate_content(
        self,
        documents: list[Document],
        config: ProcessorConfig,
        extraction_log: list[str],
    ) -> tuple[list[Document], list[str]]:
        """Validate extracted content quality.

        Parameters
        ----------
        documents : list[Document]
            Documents to validate
        config : ProcessorConfig
            Configuration for validation
        extraction_log : list[str]
            Log to append validation messages to

        Returns
        -------
        tuple[list[Document], list[str]]
            Tuple of (valid documents, error messages)
        """
        valid_docs = []
        errors = []

        # Get settings
        custom_settings = config.get("custom_settings", {})
        min_length = custom_settings.get("min_content_length", self.MIN_CONTENT_LENGTH)
        max_length = custom_settings.get("max_content_length", self.MAX_CONTENT_LENGTH)

        for doc in documents:
            text = doc.page_content

            # Check content length
            if len(text) < min_length:
                errors.append(f"Content too short ({len(text)} chars)")
                continue

            if len(text) > max_length:
                extraction_log.append(f"Content too long ({len(text)} chars), truncating")
                doc.page_content = text[:max_length]

            # Check for garbage content
            garbage_chars = len(re.findall(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]", text))
            if garbage_chars / len(text) > self.GARBAGE_RATIO_THRESHOLD:
                errors.append("Content contains too many invalid characters")
                continue

            valid_docs.append(doc)

        return valid_docs, errors

    @final
    @log_time
    def enrich_metadata(
        self,
        documents: list[Document],
        config: ProcessorConfig,
    ) -> list[Document]:
        """Enrich document metadata with common information.

        Common metadata includes:
        - Processing timestamp
        - Content hash
        - Text statistics (length, word count)
        - Language detection
        - Content type
        - Processing version/configuration
        """
        for doc in documents:
            # Add processing metadata
            doc.metadata.update(
                {
                    "processed_at": datetime.utcnow().isoformat(),
                    "processor_type": self.__class__.__name__,
                    "content_length": len(doc.page_content),
                    "word_count": len(doc.page_content.split()),
                    "content_hash": hashlib.sha256(doc.page_content.encode()).hexdigest(),
                    # Store only simple values that Pinecone accepts
                    "chunk_size": config.chunk_size,
                    "chunk_overlap": config.overlap,
                    "max_chunks": str(config.max_chunks) if config.max_chunks else "None",
                }
            )

        return documents

    @final
    @log_time
    def filter_documents(
        self,
        documents: list[Document],
        config: ProcessorConfig,
        extraction_log: list[str],
    ) -> list[Document]:
        """Filter documents based on common criteria.

        Parameters
        ----------
        documents : list[Document]
            Documents to filter
        config : ProcessorConfig
            Configuration for filtering
        extraction_log : list[str]
            Log to append filtering messages to

        Returns
        -------
        list[Document]
            Filtered documents
        """
        # Remove duplicates based on content hash
        seen_hashes = set()
        unique_docs = []

        for doc in documents:
            content_hash = doc.metadata.get("content_hash")
            if not content_hash or content_hash not in seen_hashes:
                if content_hash:
                    seen_hashes.add(content_hash)
                unique_docs.append(doc)
            else:
                extraction_log.append(
                    f"Removed duplicate content from {doc.metadata.get('source', 'unknown')}"
                )

        return unique_docs

    @final
    def track_progress(
        self,
        current: int,
        total: int,
        stage: str,
        extraction_log: list[str],
    ) -> None:
        """Track and log processing progress.

        Parameters
        ----------
        current : int
            Current progress
        total : int
            Total items to process
        stage : str
            Current processing stage
        extraction_log : list[str]
            Log to append progress messages to
        """
        percentage = (current / total) * 100 if total > 0 else 0
        extraction_log.append(f"Progress: {stage} - {current}/{total} ({percentage:.1f}%)")

    @final
    @log_time
    def process(
        self,
        *,
        file_path: str | None = None,
        file_bytes: bytes | None = None,
        config: ProcessorConfig | None = None,
    ) -> ProcessorResult:
        """Process the input data and extract text.

        This method implements the template pattern, calling the following methods
        in sequence:
        1. validate_input - Validate parameters and prepare input
        2. pre_process - Pre-process the input data
        3. extract_text - Extract text from the input
        4. validate_content - Validate extracted content
        5. chunk_text - Split text into chunks
        6. enrich_metadata - Add metadata to documents
        7. filter_documents - Remove duplicates and invalid content
        8. post_process - Final processing

        Parameters
        ----------
        file_path : str | None, optional
            Path to the file to process, by default None
        file_bytes : bytes | None, optional
            Raw bytes of the file to process, by default None
        config : ProcessorConfig | None, optional
            Configuration for the processor, by default None

        Returns
        -------
        ProcessorResult
            The result of the processing
        """
        start_time = datetime.utcnow()
        extraction_log = []
        processing_stats = {}
        config = config or ProcessorConfig()
        log_memory("Process Start")

        try:
            logger.info("Starting document processing in %s", self.__class__.__name__)
            extraction_log.append("Starting document processing")

            # Validate input
            logger.info(
                "Step 1: Validating input (file_path=%s, file_bytes=%s bytes)",
                file_path,
                len(file_bytes) if file_bytes else None,
            )
            extraction_log.append("Step 1: Validating input")
            error_result, input_data = self.validate_input(
                file_path=file_path,
                file_bytes=file_bytes,
                config=config,
                extraction_log=extraction_log,
            )
            if error_result:
                logger.error("Input validation failed")
                extraction_log.append("Input validation failed")
                return error_result

            # Pre-process input
            logger.info("Step 2: Pre-processing input")
            extraction_log.append("Step 2: Pre-processing input")
            input_data = self.pre_process(input_data)
            logger.debug("Pre-processing complete")
            extraction_log.append("Pre-processing complete")
            log_memory("After Pre-processing")

            # Extract text
            logger.info("Step 3: Extracting text")
            extraction_log.append("Step 3: Extracting text")
            documents, errors = self.extract_text(input_data, config, extraction_log)
            logger.info(
                "Text extraction complete. Documents: %d, Errors: %d", len(documents), len(errors)
            )
            extraction_log.append(
                f"Text extraction complete. Documents: {len(documents)}, Errors: {len(errors)}"
            )
            log_memory("After Text Extraction")

            if not documents:
                logger.error("No documents extracted")
                extraction_log.append("No documents extracted")
                return ProcessorResult(
                    status=ProcessorStatus.ERROR,
                    message="No text could be extracted",
                    extraction_log=extraction_log,
                    processing_stats=processing_stats,
                )

            # Track document count before processing
            processing_stats["initial_document_count"] = len(documents)
            logger.info("Initial document count: %d", len(documents))
            extraction_log.append(f"Initial document count: {len(documents)}")

            # Validate content
            logger.info("Step 4: Validating content")
            extraction_log.append("Step 4: Validating content")
            documents, content_errors = self.validate_content(documents, config, extraction_log)
            errors.extend(content_errors)
            logger.info("Content validation complete. Valid documents: %d", len(documents))
            extraction_log.append(f"Content validation complete. Valid documents: {len(documents)}")
            log_memory("After Content Validation")

            # Chunk text
            logger.info("Step 5: Chunking text")
            extraction_log.append("Step 5: Chunking text")
            documents = self.chunk_text(documents, config, extraction_log)
            processing_stats["chunks_created"] = len(documents)
            logger.info("Text chunking complete. Created %d chunks", len(documents))
            extraction_log.append(f"Text chunking complete. Created {len(documents)} chunks")
            log_memory("After Text Chunking")

            # Enrich metadata
            logger.info("Step 6: Enriching metadata")
            extraction_log.append("Step 6: Enriching metadata")
            documents = self.enrich_metadata(documents, config)
            logger.debug("Metadata enrichment complete")
            extraction_log.append("Metadata enrichment complete")
            log_memory("After Metadata Enrichment")

            # Filter documents
            logger.info("Step 7: Filtering documents")
            extraction_log.append("Step 7: Filtering documents")
            documents = self.filter_documents(documents, config, extraction_log)
            processing_stats["final_document_count"] = len(documents)
            logger.info("Document filtering complete. Final count: %d", len(documents))
            extraction_log.append(f"Document filtering complete. Final count: {len(documents)}")
            log_memory("After Document Filtering")

            # Post-process documents
            logger.info("Step 8: Post-processing")
            extraction_log.append("Step 8: Post-processing")
            documents = self.post_process(documents)
            logger.debug("Post-processing complete")
            extraction_log.append("Post-processing complete")

            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            processing_stats["processing_time_seconds"] = processing_time
            logger.info("Total processing time: %.2f seconds", processing_time)
            extraction_log.append(f"Total processing time: {processing_time:.2f} seconds")

            # Add memory stats
            mem_usage = get_memory_usage()
            processing_stats["memory_usage_mb"] = mem_usage
            logger.info("Final memory usage: %.2f MB", mem_usage)

            # Determine final status and message
            if not documents:
                status = ProcessorStatus.ERROR
                message = "No valid documents after processing"
            elif errors:
                status = ProcessorStatus.PARTIAL
                message = f"Completed with {len(errors)} errors"
            else:
                status = ProcessorStatus.OK
                message = "Successfully processed file"
            logger.info("Final status: %s, Message: %s", status, message)
            extraction_log.append(f"Final status: {status}, Message: {message}")

            # Combine all text
            logger.info("Combining all document text")
            extraction_log.append("Combining all document text")
            all_text = "\n\n".join(doc.page_content for doc in documents)
            logger.debug("Text combination complete")
            extraction_log.append("Text combination complete")
            log_memory("Process Complete")

            return ProcessorResult(
                status=status,
                message=message,
                documents=documents,
                extracted_text=all_text,
                extraction_log=extraction_log,
                processing_stats=processing_stats,
            )

        except Exception as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            processing_stats["processing_time_seconds"] = processing_time
            logger.exception("Error processing file: %s", str(e))
            extraction_log.append(f"Error processing file: {str(e)}")
            extraction_log.append(f"Error occurred after {processing_time:.2f} seconds")

            return ProcessorResult(
                status=ProcessorStatus.ERROR,
                message=str(e),
                extraction_log=extraction_log,
                processing_stats=processing_stats,
            )

    @final
    def validate_input(
        self,
        file_path: str | None,
        file_bytes: bytes | None,
        config: ProcessorConfig,
        extraction_log: list[str],
    ) -> tuple[ProcessorResult | None, str | bytes | None]:
        """Validate and prepare input data.

        Default implementation that checks for valid input parameters.
        Subclasses can extend this to add format-specific validation.
        """
        # Input validation
        if bool(file_path) == bool(file_bytes):  # both True or both False
            message = "Exactly one of file_path or file_bytes must be provided"
            extraction_log.append(message)
            return (
                ProcessorResult(
                    status=ProcessorStatus.ERROR,
                    message=message,
                    extraction_log=extraction_log,
                ),
                None,
            )

        return None, file_path if file_path else file_bytes

    def pre_process(self, input_data: str | bytes) -> str | bytes:
        """Pre-process the input data before text extraction.

        Default implementation that returns input data as is.
        Subclasses can override this to add format-specific pre-processing.
        """
        return input_data

    @abstractmethod
    @final
    def extract_text(
        self,
        input_data: str | bytes,
        config: ProcessorConfig,
        extraction_log: list[str],
    ) -> tuple[list[Document], list[str]]:
        """Extract text from the input data.

        This is the main method that each processor must implement to handle
        text extraction for their specific file type.

        Parameters
        ----------
        input_data : str | bytes
            Either a file path or raw bytes of the document
        config : ProcessorConfig
            Configuration for processing
        extraction_log : list[str]
            Log to append extraction messages to

        Returns
        -------
        tuple[list[Document], list[str]]
            A tuple containing:
            - List of extracted documents
            - List of error messages (empty if no errors)
        """
        raise NotImplementedError("Subclasses must implement extract_text")

    @final
    @log_time
    def chunk_text(
        self,
        documents: list[Document],
        config: ProcessorConfig,
        extraction_log: list[str],
    ) -> list[Document]:
        """Split documents into chunks using Langchain's text splitter.

        Uses RecursiveCharacterTextSplitter which is the most advanced splitter
        that tries to keep semantic units (like sentences) together.
        """
        chunk_size = config.chunk_size
        overlap = config.overlap
        max_chunks = config.max_chunks

        logger.info(
            "Starting text chunking with size=%d, overlap=%d, max_chunks=%s",
            chunk_size,
            overlap,
            max_chunks,
        )

        # Create text splitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            length_function=len,
            is_separator_regex=False,
            separators=["\n\n", "\n", " ", ""],  # Optimize splitting by using common separators
            keep_separator=False,  # Don't keep separators to reduce chunk size
        )

        chunked_docs = []
        for doc_idx, doc in enumerate(documents, 1):
            logger.info(
                "Processing document %d/%d (length: %d chars)",
                doc_idx,
                len(documents),
                len(doc.page_content),
            )

            # Split the document
            try:
                chunks = text_splitter.split_text(doc.page_content)
                logger.info("Created %d chunks for document %d", len(chunks), doc_idx)

                # Create Document objects for each chunk
                for i, chunk_text in enumerate(chunks, 1):
                    # Stop if we've reached max chunks
                    if max_chunks and len(chunked_docs) >= max_chunks:
                        logger.info(
                            "Reached maximum chunk count (%d), truncating remaining text",
                            max_chunks,
                        )
                        extraction_log.append(
                            f"Reached maximum chunk count ({max_chunks}), truncating remaining text"
                        )
                        break

                    try:
                        new_doc = Document(
                            page_content=chunk_text,
                            metadata={
                                **doc.metadata,
                                "chunk": i,
                                "total_chunks": len(chunks),
                                "original_doc_idx": doc_idx,
                            },
                        )
                        chunked_docs.append(new_doc)
                        logger.info("Created Document for chunk %d/%d", i, len(chunks))
                    except Exception as e:
                        logger.error("Error creating Document for chunk %d: %s", i, str(e))
                        extraction_log.append(f"Error creating chunk {i}: {str(e)}")

            except Exception as e:
                logger.error("Error splitting document %d: %s", doc_idx, str(e))
                extraction_log.append(f"Error splitting document {doc_idx}: {str(e)}")
                continue

        logger.info("Chunking complete. Created %d total chunked documents", len(chunked_docs))
        return chunked_docs

    def post_process(self, documents: list[Document]) -> list[Document]:
        """Perform final processing on the documents.

        Default implementation that returns documents as is.
        Subclasses can override this to add format-specific post-processing.
        """
        return documents
