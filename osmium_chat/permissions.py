from dataclasses import dataclass
from enum import IntFlag

from osmium_protos import PB_PermissionOverrides, PB_TypesChannelOverride


__all__: tuple[str, ...] = (
    "PermissionOverrides",
    "ChannelOverride",
    "ChannelOverrides",
    "CommunityPermission",
)


class CommunityPermission(IntFlag):
    """A bitfield of the permissions a role can grant within a community.

    Mirrors :class:`~osmium_protos.PB_CommunityPermission`. Being an
    :class:`enum.IntFlag`, members combine with ``|`` and can be tested with
    ``in``, so a role's permissions integer reads naturally::

        perms = CommunityPermission.VIEW_CHANNEL | CommunityPermission.SEND_MESSAGES
        await community.create_role("member", permissions=perms)

        if CommunityPermission.ADMINISTRATOR in CommunityPermission(role.permissions):
            ...
    """

    NO_PERMISSION = 0
    ADMINISTRATOR = 1
    VIEW_CHANNEL = 2
    SEND_MESSAGES = 4
    CONNECT_VOICE = 8
    MODIFY_CHANNEL = 16
    SEND_MEDIA = 32
    DELETE_MESSAGES = 64
    PIN_MESSAGES = 128
    SPEAK_VOICE = 256
    MODIFY_COMMUNITY = 512
    MODIFY_ROLES = 1024
    REMOVE_MEMBERS = 2048
    ADD_REACTIONS = 4096
    MODIFY_LINKED_STICKERS = 8192


@dataclass(frozen=True, slots=True)
class PermissionOverrides:
    """Allow and deny bitfields for a channel-specific override."""

    allow: CommunityPermission
    deny: CommunityPermission

    @classmethod
    def from_pb(
        cls,
        permissions: PB_PermissionOverrides | None,
    ) -> "PermissionOverrides | None":
        if permissions is None:
            return None
        return cls(
            allow=CommunityPermission(permissions.pos),
            deny=CommunityPermission(permissions.neg),
        )

    def to_pb(self) -> PB_PermissionOverrides:
        return PB_PermissionOverrides(pos=int(self.allow), neg=int(self.deny))


@dataclass(frozen=True, slots=True)
class ChannelOverride:
    """A role's permission override for one channel."""

    community_id: int
    channel_id: int
    role_id: int
    permissions: PermissionOverrides | None

    @classmethod
    def from_pb(cls, override: PB_TypesChannelOverride) -> "ChannelOverride":
        return cls(
            community_id=override.community_id,
            channel_id=override.channel_id,
            role_id=override.role_id,
            permissions=PermissionOverrides.from_pb(override.permissions),
        )


@dataclass(frozen=True, slots=True)
class ChannelOverrides:
    """The overrides returned for a channel and parent-sync state."""

    overrides: tuple[ChannelOverride, ...]
    parent_sync: bool
