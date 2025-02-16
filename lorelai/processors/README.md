# Document Processors

This package provides a flexible and extensible system for extracting and processing text from
various document types.

## Quick Start

```python
from lorelai.processors import process_file, ProcessorConfig

# Process a file with default settings
result = process_file(file_path="document.pdf")

# Process with custom configuration
config = ProcessorConfig(
    chunk_size=500,
    overlap=50,
    custom_settings={
        "start_page": 1,
        "end_page": 5,
    }
)
result = process_file(file_path="document.pdf", config=config)
```

## Documentation

For detailed documentation about:

- Architecture and design principles
- How to use the processors
- How to create new processors
- Available configuration options
- Common functionality
- Best practices

Please see [Document Processors Guide](../docs/processors.md)

## Available Processors

Currently supported document types:

- PDF files (using PyPDF2)

## Adding New Processors

To add support for a new document type:

1. Create a new processor class that inherits from `BaseProcessor`
1. Implement the required methods:
   - `supported_extensions()`
   - `supported_mimetypes()`
   - `extract_text()`
1. Register any processor-specific configuration fields

See the documentation for detailed instructions and examples.
