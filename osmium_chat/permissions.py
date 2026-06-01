from enum import IntFlag


__all__: tuple[str, ...] = (
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
