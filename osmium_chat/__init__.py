from importlib.metadata import version

__version__: str = version("osmium-chat")


# Imported after ``__version__`` is defined, since the submodules read it at
# import time.
from osmium_chat.bot import Bot
from osmium_chat.channel import Channel, ChannelType
from osmium_chat.commands import Command, CommandRestriction
from osmium_chat.community import Community
from osmium_chat.content import Bold, Code, CodeBlock, Content, Italic, Spoiler, Strikethrough, TextUrl, Underline, UnicodeEmoji
from osmium_chat.emoji import CustomEmoji
from osmium_chat.file import File
from osmium_chat.invite import Invite
from osmium_chat.context import Context
from osmium_chat.mentions import UserMention
from osmium_chat.message import Message
from osmium_chat.permissions import CommunityPermission
from osmium_chat.photo import Photo
from osmium_chat.reaction import Reaction
from osmium_chat.role import Role
from osmium_chat.user.user import User

__all__: tuple[str, ...] = (
    "__version__",
    "Bold",
    "Bot",
    "Channel",
    "ChannelType",
    "Code",
    "CodeBlock",
    "Command",
    "CommandRestriction",
    "Community",
    "CommunityPermission",
    "Content",
    "Context",
    "CustomEmoji",
    "File",
    "Invite",
    "Italic",
    "Message",
    "Photo",
    "Reaction",
    "Role",
    "Spoiler",
    "Strikethrough",
    "TextUrl",
    "Underline",
    "UnicodeEmoji",
    "User",
    "UserMention",
)
