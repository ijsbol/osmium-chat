from typing import TYPE_CHECKING

from osmium_protos import PB_Profile

from osmium_chat.photo import Photo

if TYPE_CHECKING:
    from osmium_chat.client import Client


__all__: tuple[str, ...] = (
    "Profile",
)


class Profile:
    """A user's extended profile, fetched via :meth:`User.fetch_profile`.

    Carries the fields the server only sends on an explicit profile lookup:
    the user's bio, premium status, and image banner.
    """

    __slots__: tuple[str, ...] = (
        "user_id",
        "bio",
        "premium_since",
        "banner",
    )

    def __init__(self, profile: PB_Profile, client: "Client") -> None:
        """Build a profile from a protobuf payload.

        :param profile: The raw ``PB_Profile`` to read fields from.
        :param client: The client used to download the banner.
        """
        self.user_id: int | None = profile.ref.user_id if profile.ref else None
        self.bio: str = profile.bio
        self.premium_since: int | None = profile.premium_since
        self.banner: Photo | None = (
            Photo(profile.banner, client) if profile.banner else None
        )
