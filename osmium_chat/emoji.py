"""Custom community emoji.

A :class:`CustomEmoji` represents a community-specific emoji uploaded to an
Osmium sticker pack.  It can be embedded directly in a
:class:`~osmium_chat.content.Content` message, used as a reaction, or accepted
as a command argument.

**Fetching**

Custom emojis for a community are retrieved with
:meth:`~osmium_chat.community.Community.fetch_custom_emojis`::

    emojis = await ctx.community.fetch_custom_emojis()
    emoji  = next(e for e in emojis if e.name == "wave")

**Embedding in messages**

Pass a :class:`CustomEmoji` directly to :class:`~osmium_chat.content.Content`
— it renders as the emoji name in plain text client-side and produces a
``custom_emoji`` entity span on the wire::

    await ctx.channel.send(Content("Hello! ", emoji))

**As a command argument**

Annotating a command parameter as :class:`CustomEmoji` makes the parser accept
either a ``:name:`` mention or a ``custom_emoji`` message entity at the
argument's position::

    @bot.command("react")
    async def react(ctx: Context, emoji: CustomEmoji) -> None:
        await ctx.message.add_reaction(emoji)

**Creating and deleting**

Upload a new emoji with
:meth:`~osmium_chat.community.Community.create_custom_emoji`, and remove one
with :meth:`CustomEmoji.delete`::

    emoji = await ctx.community.create_custom_emoji(image_bytes, "wave")
    await emoji.delete()
"""

from typing import TYPE_CHECKING

from osmium_protos import (
    PB_MessageEntity,
    PB_MessageEntityCustomEmojiEntity,
    PB_RemoveStickerFromPack,
    PB_StickerPackRef,
)

from osmium_chat.content import _FormattingNode, _expand

if TYPE_CHECKING:
    from osmium_chat.client import Client


__all__: tuple[str, ...] = (
    "CustomEmoji",
)


class CustomEmoji(_FormattingNode):
    """A custom emoji belonging to a community's emoji pack.

    Can be embedded directly in a :class:`~osmium_chat.content.Content` message
    — it renders as the emoji name in plain text and produces a
    ``custom_emoji`` entity span on the wire::

        content = Content("Look at this! ", emoji)

    Use :meth:`delete` to remove it from its community, and :meth:`rename` to
    update its local display name.

    :param emoji_id: The server-assigned snowflake id of this emoji.
    :param name: The emoji's short name (without colons).
    :param community_id: The id of the community this emoji belongs to.
    :param pack_id: The id of the sticker pack that holds this emoji.
    :param client: The client used to manage the emoji.
    """

    __slots__ = ("id", "name", "community_id", "_pack_id", "_client")

    def __init__(
        self,
        emoji_id: int,
        name: str,
        community_id: int,
        pack_id: int,
        client: "Client",
    ) -> None:
        super().__init__(name)
        self.id: int = emoji_id
        self.name: str = name
        self.community_id: int = community_id
        self._pack_id: int = pack_id
        self._client = client

    def _make_entity(self, start: int, length: int) -> PB_MessageEntity:
        return PB_MessageEntity(
            start_index=start,
            length=length,
            custom_emoji=PB_MessageEntityCustomEmojiEntity(emoji_id=self.id),
        )

    async def delete(self) -> None:
        """Remove this emoji from its community's emoji pack.

        :raises RequestError: If the gateway rejects the request.
        """
        await self._client.send_pb(PB_RemoveStickerFromPack(
            pack=PB_StickerPackRef(id=self._pack_id),
            sticker_id=self.id,
        ))

    def rename(self, name: str) -> "CustomEmoji":
        """Update this emoji's local display name.

        The Osmium gateway does not expose a rename endpoint, so this only
        updates the local :attr:`name` and the placeholder text used when the
        emoji is embedded in a :class:`~osmium_chat.content.Content`. The
        server-side name (set at upload time) is unchanged.

        :param name: The new short name (without colons).
        :returns: This emoji, with :attr:`name` updated.
        """
        self.name = name
        self._parts = _expand((name,))
        return self

    def __repr__(self) -> str:
        return f"CustomEmoji(id={self.id!r}, name={self.name!r})"
