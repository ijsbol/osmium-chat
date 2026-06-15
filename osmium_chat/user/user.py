from typing import TYPE_CHECKING

from osmium_protos import PB_ChatRef, PB_GetProfile, PB_User, PB_UserRef

from osmium_chat.channel import Channel
from osmium_chat.photo import Photo
from osmium_chat.user.profile import Profile
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
        "profile",
        "_client",
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
        self.photo: Photo | None = Photo(user.photo, client) if user.photo else None
        self.icon: int | None = user.icon
        self.color: int | None = user.color
        self.dm_channel: Channel = Channel(
            PB_ChatRef(user=PB_UserRef(user_id=self.id)),
            client,
        )
        self.profile: Profile | None = None
        self._client = client

    async def fetch_profile(self) -> Profile:
        """Fetch this user's extended profile and cache it on :attr:`profile`.

        Calls ``users.getProfile`` and wraps the result in a :class:`Profile`,
        which carries the user's bio, premium status, and image banner.

        :returns: The fetched :class:`Profile`.
        :raises RequestError: If the gateway rejects the request.
        """
        result = await self._client.request(PB_GetProfile(
            ref=PB_UserRef(user_id=self.id),
        ))
        assert result.profile is not None
        self.profile = Profile(result.profile, self._client)
        return self.profile
