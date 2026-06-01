from enum import IntEnum

from osmium_protos import PB_UserStatusActivity


__all__: tuple[str, ...] = (
    "UserActivityType",
    "UserStatusActivity",
)


class UserActivityType(IntEnum):
    """The kind of activity a user is engaged in."""

    GAME = 0
    STREAMING = 1
    LISTENING = 2
    WATCHING = 3


class UserStatusActivity:
    """A single activity shown in a user's status (e.g. a game being played)."""

    __slots__: tuple[str, ...] = (
        "title",
        "type",
        "start_time",
        "end_time",
        "state",
    )

    def __init__(self, activity: PB_UserStatusActivity) -> None:
        """Build an activity from a protobuf payload.

        :param activity: The raw ``PB_UserStatusActivity`` to read fields from.
        """
        self.title: str = activity.title
        self.type: UserActivityType = UserActivityType(activity.type)
        self.start_time: int = activity.start_time
        self.end_time: int | None = activity.end_time
        self.state: str | None = activity.state
