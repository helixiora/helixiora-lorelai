# Document Processors Guide

The document processors system provides a flexible and extensible way to extract and process text
from various document types. It uses a template pattern to standardize document processing while
allowing for type-specific customization.

## Table of Contents

- [Architecture](#architecture)
- [Using Processors](#using-processors)
- [Configuration](#configuration)
- [Creating New Processors](#creating-new-processors)
- [Common Functionality](#common-functionality)
- [Best Practices](#best-practices)

## Architecture

The system consists of several key components:

### Base Processor

The `BaseProcessor` class provides the template for all document processors. It implements a
standard workflow:

1. Input validation
1. Pre-processing
1. Text extraction
1. Content validation
1. Text chunking
1. Metadata enrichment
1. Document filtering
1. Post-processing

### Configuration System

The `ProcessorConfig` class provides a flexible configuration system that supports:

- Common settings for all processors
- Processor-specific settings
- Runtime validation
- Default values

### Registry

The `ProcessorRegistry` manages processor selection and provides a single entry point for processing
files:

- Automatic processor selection based on file type
- MIME type detection
- Centralized error handling

## Using Processors

### Basic Usage

```python
from lorelai.processors import process_file

# Process a file with default settings
result = process_file(file_path="document.pdf")

# Check the result
if result.status == "ok":
    # Access extracted text
    print(result.extracted_text)

    # Access individual documents
    for doc in result.documents:
        print(f"Document {doc.metadata['chunk']}")
        print(doc.page_content)
```

### With Configuration

```python
from lorelai.processors import process_file, ProcessorConfig

# Create configuration
config = ProcessorConfig(
    # Common settings
    chunk_size=500,      # Size of text chunks
    overlap=50,          # Overlap between chunks
    max_chunks=100,      # Maximum chunks to create

    # Processor-specific settings
    custom_settings={
        "start_page": 1,
        "end_page": 5,
    }
)

# Process with configuration
result = process_file(
    file_path="document.pdf",
    config=config
)
```

### Processing Statistics

```python
# Access processing statistics
stats = result.processing_stats
print(f"Processing time: {stats['processing_time_seconds']}s")
print(f"Initial documents: {stats['initial_document_count']}")
print(f"Chunks created: {stats['chunks_created']}")
print(f"Final documents: {stats['final_document_count']}")

# Access processing log
for entry in result.extraction_log:
    print(entry)
```

## Configuration

### Common Settings

| Setting | Type | Default | Description | |---------|------|---------|-------------| | chunk_size |
int | 1000 | Size of text chunks | | overlap | int | 100 | Characters to overlap between chunks | |
max_chunks | int | None | Maximum chunks to create | | min_content_length | int | 10 | Minimum
characters for valid content | | max_content_length | int | 1,000,000 | Maximum characters to
process |

### PDF-Specific Settings

| Setting | Type | Default | Description | |---------|------|---------|-------------| | start_page |
int | 1 | First page to process | | end_page | int | None | Last page to process |

## Creating New Processors

To add support for a new document type:

1. Create a new processor class:

```python
from lorelai.processors import BaseProcessor, ProcessorConfig

class MyProcessor(BaseProcessor):
    """Processor for my document type."""

    @classmethod
    def supported_extensions(cls) -> list[str]:
        return [".mydoc"]

    @classmethod
    def supported_mimetypes(cls) -> list[str]:
        return ["application/x-mydoc"]

    def extract_text(
        self,
        input_data: str | bytes,
        config: ProcessorConfig,
        extraction_log: list[str],
    ) -> tuple[list[Document], list[str]]:
        # Implement text extraction here
        ...
```

1. Register processor-specific settings:

```python
from lorelai.processors import ProcessorConfig

# Register settings
ProcessorConfig.register_field(
    "my_setting",
    str,
    "default_value",
    "Description of my setting"
)
```

1. Use common functionality:

```python
def extract_text(self, ...):
    # Track progress
    self.track_progress(current, total, "My stage", extraction_log)

    # Clean extracted text
    text = self.clean_text(raw_text)

    # Create document
    doc = Document(
        page_content=text,
        metadata={...}
    )
```

## Common Functionality

### Text Cleaning

- Unicode normalization
- Control character removal
- Whitespace normalization
- Common OCR artifact fixes

### Content Validation

- Length checks
- Garbage content detection
- Quality thresholds
- Error classification

### Metadata Enrichment

- Processing timestamps
- Content hashes
- Text statistics
- Processing configuration

### Document Filtering

- Duplicate detection
- Content quality filtering
- Empty content removal

### Progress Tracking

- Stage-based progress
- Percentage completion
- Detailed logging

## Best Practices

### Error Handling

- Always return meaningful error messages
- Use the extraction log for detailed information
- Set appropriate status (OK/ERROR/PARTIAL)

### Configuration best practices

- Register all processor-specific settings
- Provide sensible defaults
- Validate configuration values

### Metadata

- Include source-specific metadata
- Add processing information
- Maintain original document structure

### Performance

- Use progress tracking for long operations
- Implement resource management
- Handle large documents appropriately

### Text Quality

- Clean and normalize text
- Remove invalid content
- Handle encoding issues

### Testing

- Test with various input types
- Verify error handling
- Check configuration validation
- Validate output quality
