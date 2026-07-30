"""Members of group chats and community channel member lists."""

from typing import TYPE_CHECKING

from osmium_protos import PB_ChatMember, PB_User

from osmium_chat.user.user import User

if TYPE_CHECKING:
    from osmium_chat.channel import Channel
    from osmium_chat.client import Client


__all__: tuple[str, ...] = ("ChatMember",)


class ChatMember:
    """A user participating in a chat, with optional chat permissions."""

    __slots__: tuple[str, ...] = (
        "user",
        "permissions",
        "nickname",
        "channel",
        "_client",
    )

    def __init__(
        self,
        user: User,
        client: "Client",
        *,
        permissions: int | None = None,
        nickname: str | None = None,
        channel: "Channel | None" = None,
    ) -> None:
        self.user = user
        self.permissions = permissions
        self.nickname = nickname
        self.channel = channel
        self._client = client

    @property
    def id(self) -> int:
        return self.user.id

    @property
    def display_name(self) -> str:
        return self.nickname or self.user.name

    @classmethod
    def from_pb(
        cls,
        member: PB_ChatMember,
        user: PB_User | None,
        client: "Client",
        *,
        channel: "Channel | None" = None,
    ) -> "ChatMember":
        return cls(
            User(user if user is not None else PB_User(id=member.user_id), client),
            client,
            permissions=member.permissions,
            channel=channel,
        )

    async def edit(self, permissions: int) -> "ChatMember":
        """Replace this member's chat permission bitfield."""
        if self.channel is None:
            raise ValueError("Cannot edit a member without its channel")
        await self.channel.edit_member(self.id, permissions)
        self.permissions = permissions
        return self

    async def remove(self) -> None:
        """Remove this member from its chat."""
        if self.channel is None:
            raise ValueError("Cannot remove a member without its channel")
        await self.channel.remove_member(self.id)
