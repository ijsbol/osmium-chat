from enum import IntEnum
from typing import TYPE_CHECKING

from osmium_protos import PB_CreatedInvite, PB_DeleteChatInvite, PB_InvitePreview

if TYPE_CHECKING:
    from osmium_chat.client import Client


__all__: tuple[str, ...] = (
    "Invite",
    "InvitePreview",
    "InviteType",
)


class InviteType(IntEnum):
    """The type of entity an invite links to.

    Mirrors :class:`~osmium_protos.PB_InviteType`.
    """

    UNKNOWN = 0
    COMMUNITY = 1
    GROUP = 2
    USER = 3


class Invite:
    """A channel invite handle that can be revoked.

    Holds the invite :attr:`code` returned by the gateway. Call :meth:`delete`
    to revoke it. For the full hydrated metadata use
    :class:`InvitePreview` instead.
    """

    __slots__: tuple[str, ...] = (
        "code",
        "_client",
    )

    def __init__(self, invite: PB_CreatedInvite, client: "Client") -> None:
        """Build an invite from a protobuf payload.

        :param invite: The raw ``PB_CreatedInvite`` returned by the gateway.
        :param client: The client used to manage the invite.
        """
        self.code: str = invite.code
        self._client = client

    async def delete(self) -> None:
        """Revoke this invite."""
        await self._client.send_pb(PB_DeleteChatInvite(code=self.code))


class InvitePreview:
    """A hydrated invite including creator and target metadata.

    Returned by :meth:`~osmium_chat.channel.Channel.create_invite` and
    :meth:`~osmium_chat.channel.Channel.get_invites`. Call :meth:`delete`
    to revoke it.
    """

    __slots__: tuple[str, ...] = (
        "code",
        "creator_id",
        "target_id",
        "target_type",
        "expires_at",
        "_client",
    )

    def __init__(self, preview: PB_InvitePreview, client: "Client") -> None:
        """Build an invite preview from a protobuf payload.

        :param preview: The raw ``PB_InvitePreview`` returned by the gateway.
        :param client: The client used to manage the invite.
        """
        self.code: str = preview.code
        self.creator_id: int = preview.creator_id
        self.target_id: int = preview.target_id
        self.target_type: InviteType = InviteType(preview.target_type)
        self.expires_at: int | None = preview.expires_at
        self._client = client

    async def delete(self) -> None:
        """Revoke this invite."""
        await self._client.send_pb(PB_DeleteChatInvite(code=self.code))
