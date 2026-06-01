from osmium_protos import PB_User

from osmium_chat.photo import Photo
from osmium_chat.user.status import UserStatus


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
    )

    def __init__(self, user: PB_User) -> None:
        """Build a user from a protobuf payload.

        :param user: The raw ``PB_User`` to read fields from.
        """
        self.id: int = user.id
        self.name: str = user.name
        self.username: str | None = user.username
        self.status: UserStatus | None = UserStatus(user.status) if user.status else None
        self.photo: Photo | None = Photo(user.photo) if user.photo else None
        self.icon: int | None = user.icon
        self.color: int | None = user.color
