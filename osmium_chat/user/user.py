from typing import TYPE_CHECKING

from osmium_protos import PB_ChatRef, PB_User, PB_UserRef

from osmium_chat.channel import Channel
from osmium_chat.photo import Photo
from osmium_chat.user.status import UserStatus

if TYPE_CHECKING:
    from osmium_chat.client import Client


__all__: tuple[str, ...] = (
    "User",
)


class User:
    """An Osmium user, parsed from its protobuf representation."""

    __slots__: tuple[str, ...] = (
        "id",
        "name",
        "username",
        "status",
        "photo",
        "icon",
        "color",
        "dm_channel",
    )

    def __init__(self, user: PB_User, client: "Client") -> None:
        """Build a user from a protobuf payload.

        :param user: The raw ``PB_User`` to read fields from.
        :param client: The client used to deliver messages to this user.
        """
        self.id: int = user.id
        self.name: str = user.name
        self.username: str | None = user.username
        self.status: UserStatus | None = UserStatus(user.status) if user.status else None
        self.photo: Photo | None = Photo(user.photo) if user.photo else None
        self.icon: int | None = user.icon
        self.color: int | None = user.color
        self.dm_channel: Channel = Channel(
            PB_ChatRef(user=PB_UserRef(user_id=self.id)),
            client,
        )
