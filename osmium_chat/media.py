"""Wrappers for media entries and server-generated embeds."""

from typing import TYPE_CHECKING

from osmium_protos import PB_File, PB_MessageMedia, PB_MediaEmbed

from osmium_chat.file import File

if TYPE_CHECKING:
    from osmium_chat.client import Client


__all__: tuple[str, ...] = ("MediaEmbed", "MessageMedia")


class MediaEmbed:
    """A rich link preview attached to a message."""

    __slots__: tuple[str, ...] = (
        "url",
        "title",
        "description",
        "file",
        "image_variant",
        "author_name",
        "website_name",
    )

    def __init__(self, embed: PB_MediaEmbed, client: "Client") -> None:
        self.url: str = embed.url
        self.title: str | None = embed.title
        self.description: str | None = embed.description
        self.file: File | None = (
            File(embed.file, client) if embed.file is not None else None
        )
        self.image_variant: str | None = embed.image_variant
        self.author_name: str | None = embed.author_name
        self.website_name: str | None = embed.website_name


class MessageMedia:
    """One media entry, containing either a file or an embed."""

    __slots__: tuple[str, ...] = ("file", "embed")

    def __init__(self, media: PB_MessageMedia, client: "Client") -> None:
        self.file: File | None = (
            File(media.file.file, client)
            if media.file is not None and media.file.file is not None
            else None
        )
        self.embed: MediaEmbed | None = (
            MediaEmbed(media.embed, client) if media.embed is not None else None
        )

    @classmethod
    def from_file(cls, file: PB_File, client: "Client") -> "MessageMedia":
        from osmium_protos import PB_MediaFile

        return cls(PB_MessageMedia(file=PB_MediaFile(file=file)), client)
