"""Message reaction model.

A :class:`Reaction` groups every user who reacted to a message with the same
emoji into one object.  The :attr:`~Reaction.emoji` is either a
:class:`~osmium_chat.content.UnicodeEmoji` (standard Unicode) or a
:class:`~osmium_chat.emoji.CustomEmoji` stub (community emoji).

**Reading reactions**

Reactions arrive in :attr:`~osmium_chat.message.Message.reactions` after a
message is parsed from the gateway::

    for reaction in message.reactions:
        print(reaction.emoji, reaction.count, reaction.users)

**Adding and removing reactions**

Use :meth:`~osmium_chat.message.Message.add_reaction` and
:meth:`~osmium_chat.message.Message.remove_reaction` to react to a message.
Both accept a plain Unicode string, a :class:`~osmium_chat.content.UnicodeEmoji`,
or a :class:`~osmium_chat.emoji.CustomEmoji`::

    await message.add_reaction("👍")
    await message.add_reaction(UnicodeEmoji("🎉"))
    await message.add_reaction(custom_emoji)
    await message.remove_reaction("👍")

.. note::

   The :attr:`~Reaction.users` list is a gateway-provided preview and may be
   truncated for reactions with many participants.  :attr:`~Reaction.count` is
   always the authoritative total.
"""

from typing import TYPE_CHECKING

from osmium_protos import PB_MessageReactionField

from osmium_chat.content import UnicodeEmoji

if TYPE_CHECKING:
    from osmium_chat.emoji import CustomEmoji


__all__: tuple[str, ...] = (
    "Reaction",
)


class Reaction:
    """A single reaction type on a message.

    Groups all users who reacted with the same emoji under one
    :class:`Reaction`. The :attr:`emoji` is either a
    :class:`~osmium_chat.content.UnicodeEmoji` (for standard Unicode emoji) or
    a :class:`~osmium_chat.emoji.CustomEmoji` stub carrying only the server id
    (for community custom emoji received from the gateway). :attr:`users` holds
    the preview list of user ids the gateway provided — it may be truncated for
    reactions with many participants.

    :param emoji: The emoji this reaction represents.
    :param count: Total number of users who added this reaction.
    :param users: Preview list of user ids who added this reaction.
    """

    __slots__ = ("emoji", "count", "users")

    def __init__(
        self,
        emoji: "CustomEmoji | UnicodeEmoji",
        count: int,
        users: list[int],
    ) -> None:
        self.emoji: "CustomEmoji | UnicodeEmoji" = emoji
        self.count: int = count
        self.users: list[int] = users

    def __repr__(self) -> str:
        return f"Reaction(emoji={self.emoji!r}, count={self.count!r})"


def _reaction_from_field(
    field: PB_MessageReactionField,
    community_id: int = 0,
) -> "Reaction":
    """Build a :class:`Reaction` from a raw protobuf field.

    Custom emoji reactions are returned as a minimal
    :class:`~osmium_chat.emoji.CustomEmoji` stub (id only, no client, no pack)
    since the full metadata is not available in a reaction update.
    """
    pb_emoji = field.emoji
    if pb_emoji is not None and pb_emoji.custom_emoji is not None:
        from osmium_chat.emoji import CustomEmoji
        emoji: "CustomEmoji | UnicodeEmoji" = CustomEmoji(
            emoji_id=pb_emoji.custom_emoji,
            name=str(pb_emoji.custom_emoji),
            community_id=community_id,
            pack_id=0,
            client=None,  # type: ignore[arg-type]
        )
    else:
        raw = (pb_emoji.unicode_emoji or "") if pb_emoji is not None else ""
        emoji = UnicodeEmoji(raw)

    return Reaction(
        emoji=emoji,
        count=field.count,
        users=list(field.preview_user_ids),
    )
