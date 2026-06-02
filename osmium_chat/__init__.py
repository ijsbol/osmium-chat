import tomllib
from pathlib import Path


def _get_version() -> str:
    """Read the package version from the project's ``pyproject.toml``.

    Supports both PEP 621 (``[project]``) and Poetry (``[tool.poetry]``) layouts.
    """
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with pyproject.open("rb") as f:
        data = tomllib.load(f)
    project = data.get("project")
    if project is not None and "version" in project:
        return project["version"]
    return data["tool"]["poetry"]["version"]


__version__: str = _get_version()


# Imported after ``__version__`` is defined, since the submodules read it at
# import time.
from osmium_chat.bot import Bot
from osmium_chat.channel import Channel, ChannelType
from osmium_chat.commands import Command, CommandRestriction
from osmium_chat.community import Community
from osmium_chat.content import Bold, Code, CodeBlock, Content, Italic, Spoiler, Strikethrough, TextUrl, Underline
from osmium_chat.file import File
from osmium_chat.invite import Invite
from osmium_chat.context import Context
from osmium_chat.message import Message
from osmium_chat.permissions import CommunityPermission
from osmium_chat.photo import Photo
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
    "File",
    "Invite",
    "Italic",
    "Message",
    "Photo",
    "Role",
    "Spoiler",
    "Strikethrough",
    "TextUrl",
    "Underline",
    "User",
)
