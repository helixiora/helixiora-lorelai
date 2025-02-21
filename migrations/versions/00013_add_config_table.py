"""add_config_table.

Revision ID: 00013
Revises: 00012
Create Date: 2025-01-27 16:48:22.867845

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "00013"
down_revision: str | None = "00012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade the database schema."""
    op.create_table(
        "config",
        sa.Column("config_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            onupdate=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("config_id"),
        sa.UniqueConstraint("key"),
    )

    # Add default prompt templates
    config_table = sa.table(
        "config",
        sa.Column("key", sa.String(length=255)),
        sa.Column("value", sa.Text()),
        sa.Column("description", sa.Text()),
    )

    # OpenAI prompt template
    openai_prompt = """You are a helpful AI assistant named Lorelai. You help users by answering
their questions based on the context provided.

Context from various sources:
{context_doc_text}

{conversation_history}
Current question: {question}

Provide a clear and concise answer based on the context above. If the question refers to previous
messages in the conversation, use that context to provide a more relevant answer. If you cannot
find the answer in the context, say so. Do not make up information.

You must respond with a JSON object that matches this schema:
{format_instructions}

Make sure to:
1. Include all relevant sources in the sources list
2. Explain your reasoning process
3. Format the answer text using markdown
4. Only include sources that were actually used in the answer
5. Provide specific relevance explanations for each source"""

    # Ollama prompt template
    ollama_prompt = """You are a helpful AI assistant named Lorelai. You help users by answering
their questions based on the context provided.

Context from various sources:
{context_doc_text}

{conversation_history}
Current question: {question}

Please provide a clear and concise answer based on the context above. If the question refers to
previous messages in the conversation, use that context to provide a more relevant answer. If you
cannot find the answer in the context, say so. Do not make up information.

Format your response in markdown, and include a "### Sources" section at the end listing the
relevant sources used to answer the question."""

    op.bulk_insert(
        config_table,
        [
            {
                "key": "openai_prompt_template",
                "value": openai_prompt,
                "description": "Prompt template for OpenAI models, includes JSON schema for structured output",  # noqa: E501
            },
            {
                "key": "ollama_prompt_template",
                "value": ollama_prompt,
                "description": "Prompt template for Ollama models, uses markdown formatting for output",  # noqa: E501
            },
        ],
    )


def downgrade() -> None:
    """Downgrade the database schema."""
    op.drop_table("config")
