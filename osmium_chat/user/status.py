from enum import IntEnum

from osmium_protos import PB_UserStatus

from osmium_chat.user.activity import UserStatusActivity


__all__: tuple[str, ...] = (
    "UserStatusStatus",
    "UserStatus",
)


class UserStatusStatus(IntEnum):
    """A user's availability state."""

    ONLINE = 0
    IDLE = 1


class UserStatus:
    """A user's presence: online flag, status state, and activities."""

    __slots__: tuple[str, ...] = (
        "online",
        "status",
        "activities",
    )

    def __init__(self, status: PB_UserStatus) -> None:
        """Build a status from a protobuf payload.

        :param status: The raw ``PB_UserStatus`` to read fields from.
        """
        self.online: bool = status.online
        self.status: UserStatusStatus | None = UserStatusStatus(status.status) if status.status else None
        self.activities: list[UserStatusActivity] = [UserStatusActivity(activity) for activity in status.activities]
