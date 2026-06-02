"""Mention formatting nodes for embedding @user mentions in outbound messages."""

from typing import TYPE_CHECKING

from osmium_protos import PB_MessageEntity

from osmium_chat.content import _FormattingNode

if TYPE_CHECKING:
    from osmium_chat.user.user import User


__all__: tuple[str, ...] = ("UserMention",)


class UserMention(_FormattingNode):
    """A @mention of a user by username, embedded in a :class:`~osmium_chat.content.Content`.

    The plain-text representation is ``@{username}``; on the wire the span is
    tagged with the ``username`` entity so clients render it as a clickable
    mention::

        await ctx.channel.send(Content("Hey ", UserMention(user), "!"))

    :param user: The user to mention.
    """

    __slots__ = ()

    def __init__(self, user: "User") -> None:
        super().__init__(f"@{user.username or user.name}")

    def _make_entity(self, start: int, length: int) -> PB_MessageEntity:
        return PB_MessageEntity(
            start_index=start,
            length=length,
            username=True,
        )
