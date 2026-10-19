from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from osmium_protos import (
    PB_DownloadFilePart,
    PB_File,
    PB_FileMetadata,
    PB_FileRef,
    PB_FileRefMediaFileRef,
)

if TYPE_CHECKING:
    from osmium_chat.client import Client


__all__: tuple[str, ...] = (
    "AudioMetadata",
    "File",
    "FileMetadata",
    "FileMarkerMetadata",
    "ImageMetadata",
    "VideoMetadata",
    "CustomEmojiMetadata",
)

# 1 MiB per download request.
_DOWNLOAD_CHUNK_SIZE: int = 1024 * 1024


@dataclass(frozen=True, slots=True)
class ImageMetadata:
    width: int
    height: int
    preview: bytes | None
    animated: bool


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    width: int
    height: int
    duration: int


@dataclass(frozen=True, slots=True)
class AudioMetadata:
    duration: int


@dataclass(frozen=True, slots=True)
class CustomEmojiMetadata:
    width: int
    height: int
    emoji: str
    pack_id: int | None
    animated: bool


@dataclass(frozen=True, slots=True)
class FileMarkerMetadata:
    """Marker metadata for a generic file attachment."""


class FileMetadata:
    """The typed metadata oneof attached to a media file."""

    __slots__: tuple[str, ...] = (
        "image",
        "video",
        "audio",
        "file",
        "custom_emoji",
    )

    def __init__(self, metadata: PB_FileMetadata) -> None:
        self.image = (
            ImageMetadata(
                metadata.image.width,
                metadata.image.height,
                metadata.image.preview,
                metadata.image.animated,
            )
            if metadata.image is not None
            else None
        )
        self.video = (
            VideoMetadata(
                metadata.video.width,
                metadata.video.height,
                metadata.video.duration,
            )
            if metadata.video is not None
            else None
        )
        self.audio = (
            AudioMetadata(metadata.audio.duration)
            if metadata.audio is not None
            else None
        )
        self.file: FileMarkerMetadata | None = (
            FileMarkerMetadata() if metadata.file is not None else None
        )
        self.custom_emoji = (
            CustomEmojiMetadata(
                metadata.custom_emoji.width,
                metadata.custom_emoji.height,
                metadata.custom_emoji.emoji,
                metadata.custom_emoji.pack.id
                if metadata.custom_emoji.pack is not None
                else None,
                metadata.custom_emoji.animated,
            )
            if metadata.custom_emoji is not None
            else None
        )

    @property
    def kind(self) -> str:
        if self.image is not None:
            return "image"
        if self.video is not None:
            return "video"
        if self.audio is not None:
            return "audio"
        if self.custom_emoji is not None:
            return "custom_emoji"
        return "file"


class File:
    """A file attachment on a received message.

    Wraps the :class:`~osmium_protos.PB_File` metadata the server sends
    alongside a message.  Call :meth:`download` to fetch the raw bytes.
    """

    __slots__: tuple[str, ...] = (
        "file_id",
        "region",
        "size",
        "mimetype",
        "filename",
        "metadata",
        "_client",
    )

    def __init__(self, file: PB_File, client: "Client") -> None:
        """Build a file attachment from a protobuf payload.

        :param file: The raw ``PB_File`` to read fields from.
        :param client: The client used to download the file.
        """
        self.file_id: int = file.file_id
        self.region: int = file.region
        self.size: int = file.size
        self.mimetype: str = file.mimetype
        self.filename: str | None = file.filename
        self.metadata: FileMetadata | None = (
            FileMetadata(file.metadata) if file.metadata is not None else None
        )
        self._client = client

    @property
    def animated(self) -> bool:
        """Whether image or custom emoji metadata marks this file animated."""
        if self.metadata is None:
            return False
        if self.metadata.image is not None:
            return self.metadata.image.animated
        if self.metadata.custom_emoji is not None:
            return self.metadata.custom_emoji.animated
        return False

    async def download(self) -> bytes:
        """Fetch and return the full file contents as :class:`bytes`.

        Requests the file in :data:`_DOWNLOAD_CHUNK_SIZE`-byte windows and
        reassembles them in order.

        :returns: The complete file bytes.
        :raises RequestError: If the gateway rejects any part request.
        """
        file_ref = PB_FileRef(media_file=PB_FileRefMediaFileRef(file_id=self.file_id))
        chunks: list[bytes] = []
        offset = 0
        while offset < self.size:
            length = min(_DOWNLOAD_CHUNK_SIZE, self.size - offset)
            result = await self._client.request(
                PB_DownloadFilePart(
                    file_ref=file_ref,
                    offset=offset,
                    length=length,
                )
            )
            part = result.file_part
            if part is None or not part.data:
                break
            chunks.append(part.data)
            offset += len(part.data)
        return b"".join(chunks)

    async def save(self, path: "str | Path | None" = None) -> Path:
        """Download the file and write it to disk.

        :param path: Destination path.  Pass a directory to write
            ``<dir>/<filename>`` using the server-provided name, or a full file
            path to control the exact location.  Defaults to the current working
            directory with the server-provided name (or ``file_<id>`` when the
            server did not supply one).
        :returns: The :class:`~pathlib.Path` the file was written to.
        :raises RequestError: If the gateway rejects any part request.
        """
        dest = Path(path) if path is not None else Path(".")
        if dest.is_dir():
            dest = dest / (self.filename or f"file_{self.file_id}")
        dest.write_bytes(await self.download())
        return dest
