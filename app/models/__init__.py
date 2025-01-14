"""Models package initialization."""

from app.database import db

# Import all models here
from .user import User
from .organisation import Organisation
from .role import Role, UserRole
from .profile import Profile
from .plan import Plan, UserPlan
from .chat import ChatMessage, ChatConversation
from .datasource import Datasource
from .google_drive import GoogleDriveItem
from .indexing import IndexingRun, IndexingRunItem
from .notification import Notification
from .extra_messages import ExtraMessages
from .user_auth import UserAuth
from .user_api_key import UserAPIKey
from .user_login import UserLogin

# List all models for easy access
__all__ = [
    "db",
    "User",
    "Organisation",
    "Role",
    "UserRole",
    "Profile",
    "Plan",
    "UserPlan",
    "ChatMessage",
    "ChatConversation",
    "Datasource",
    "GoogleDriveItem",
    "IndexingRun",
    "IndexingRunItem",
    "Notification",
    "ExtraMessages",
    "UserAuth",
    "UserAPIKey",
    "UserLogin",
]
