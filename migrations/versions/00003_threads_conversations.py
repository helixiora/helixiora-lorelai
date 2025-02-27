"""Move from threads to conversations.

Revision ID: 00004
Revises: 00003
Create Date: 2024-11-10 15:57:49.745425

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "00004"
down_revision = "00003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade the database."""
    # -- Rename table
    # RENAME TABLE chat_threads TO chat_conversations;

    # -- Rename columns
    # ALTER TABLE chat_conversations
    #     CHANGE COLUMN thread_id conversation_id varchar(50) NOT NULL;

    # ALTER TABLE chat_messages
    #     CHANGE COLUMN thread_id conversation_id varchar(50) NOT NULL;

    # ALTER TABLE chat_conversations
    #     CHANGE COLUMN marked_deleted marked_deleted BOOLEAN DEFAULT FALSE;

    # ALTER TABLE chat_conversations
    #     CHANGE COLUMN thread_name conversation_name VARCHAR(255) NULL;

    # -- Drop existing foreign key
    # ALTER TABLE chat_messages
    #      DROP FOREIGN KEY chat_messages_ibfk_1;

    # -- Add new foreign key
    # ALTER TABLE chat_messages
    #      ADD CONSTRAINT fk_chat_messages_conversation
    #      FOREIGN KEY (conversation_id)
    #      REFERENCES chat_conversations(conversation_id);

    print("upgrading")

    print("renaming table")
    op.rename_table("chat_threads", "chat_conversations")
    print("altering column")
    op.alter_column("chat_conversations", "thread_id", new_column_name="conversation_id")
    op.alter_column("chat_conversations", "thread_name", new_column_name="conversation_name")
    op.alter_column("chat_messages", "thread_id", new_column_name="conversation_id")

    print("dropping constraint")
    op.drop_constraint("chat_messages_ibfk_1", "chat_messages", type_="foreignkey")
    print("creating foreign key")
    op.create_foreign_key(
        None,
        "chat_messages",
        "chat_conversations",
        ["conversation_id"],
        ["conversation_id"],
    )
    print("done")


def downgrade() -> None:
    """Downgrade the database."""
    print("downgrading")

    print("renaming table")
    op.rename_table("chat_conversations", "chat_threads")
    print("altering column")
    op.alter_column("chat_threads", "conversation_id", new_column_name="thread_id")
    op.alter_column("chat_messages", "conversation_id", new_column_name="thread_id")
    print("dropping constraint")
    op.drop_constraint(None, "chat_messages", type_="foreignkey")
    print("creating foreign key")
    op.create_foreign_key(
        "chat_messages_ibfk_1",
        "chat_messages",
        "chat_threads",
        ["thread_id"],
        ["thread_id"],
    )
    print("done")
