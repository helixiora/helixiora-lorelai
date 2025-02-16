"""Configuration system for document processors.

This module provides a flexible configuration system that supports both
common settings for all processors and processor-specific settings.

For usage instructions and documentation, see:
- Quick start: README.md in this directory
- Detailed guide: /docs/processors.md
- Configuration reference: /docs/processors.md#configuration

Example:
    >>> from lorelai.processors import ProcessorConfig
    >>> config = ProcessorConfig(
    ...     chunk_size=500,
    ...     custom_settings={"start_page": 1}
    ... )
"""

from typing import Any, ClassVar
from pydantic import BaseModel, Field, model_validator


class ProcessorConfig(BaseModel):
    """Base configuration for all document processors.

    This class provides common configuration options for all processors
    and allows processors to add their own specific settings dynamically.

    Common settings include:
    - chunk_size: Size of text chunks to split documents into
    - overlap: Number of characters to overlap between chunks
    - max_chunks: Maximum number of chunks to process
    - custom_settings: Dictionary for processor-specific settings
    """

    # Common settings for all processors
    chunk_size: int = Field(
        default=1000,
        description="Size of text chunks to split documents into",
        ge=1,
    )
    overlap: int = Field(
        default=100,
        description="Number of characters to overlap between chunks",
        ge=0,
    )
    max_chunks: int | None = Field(
        default=None,
        description="Maximum number of chunks to process. None means no limit.",
    )

    # Dynamic settings specific to each processor
    custom_settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Processor-specific settings",
    )

    # Class variable to store processor-specific field definitions
    _field_definitions: ClassVar[dict[str, tuple[Any, Any]]] = {}

    @classmethod
    def register_field(
        cls, field_name: str, field_type: Any, default_value: Any, description: str | None = None
    ) -> None:
        """Register a new field for a specific processor.

        This method allows processors to register their specific configuration
        fields, which will be accessible through the custom_settings dictionary.

        Parameters
        ----------
        field_name : str
            Name of the field to register
        field_type : Any
            Type of the field (e.g., int, str, etc.)
        default_value : Any
            Default value for the field
        description : str | None, optional
            Description of the field, by default None
        """
        cls._field_definitions[field_name] = (field_type, default_value, description)

    @model_validator(mode="after")
    def validate_custom_settings(self) -> "ProcessorConfig":
        """Validate custom settings against registered field definitions.

        This validator ensures that:
        1. All required fields are present with correct types
        2. Default values are set for missing fields
        3. No unknown fields are present

        Returns
        -------
        ProcessorConfig
            The validated configuration object
        """
        # Create a new dictionary for validated settings
        validated_settings = {}

        # Add default values for missing fields
        for field_name, (field_type, default_value, _) in self._field_definitions.items():
            if field_name not in self.custom_settings:
                validated_settings[field_name] = default_value
            else:
                value = self.custom_settings[field_name]
                # Validate type and convert if necessary
                if not isinstance(value, field_type):
                    try:
                        value = field_type(value)
                    except (ValueError, TypeError) as e:
                        raise ValueError(
                            f"Invalid type for {field_name}. Expected {field_type.__name__}, "
                            f"got {type(value).__name__}"
                        ) from e
                validated_settings[field_name] = value

        # Check for unknown fields
        unknown_fields = set(self.custom_settings.keys()) - set(self._field_definitions.keys())
        if unknown_fields:
            raise ValueError(f"Unknown configuration fields: {unknown_fields}")

        self.custom_settings = validated_settings
        return self

    def get(self, field_name: str, default: Any = None) -> Any:
        """Get a configuration value, either common or processor-specific.

        Parameters
        ----------
        field_name : str
            Name of the configuration field
        default : Any, optional
            Default value if field is not found, by default None

        Returns
        -------
        Any
            The configuration value
        """
        # First check common settings
        if hasattr(self, field_name):
            return getattr(self, field_name)

        # Then check custom settings
        return self.custom_settings.get(field_name, default)


# Register PDF-specific fields
ProcessorConfig.register_field(
    "start_page",
    int,
    1,
    "First page to process (1-indexed)",
)
ProcessorConfig.register_field(
    "end_page",
    int | None,
    None,
    "Last page to process. If None, process all pages.",
)
