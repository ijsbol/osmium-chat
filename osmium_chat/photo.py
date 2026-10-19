from typing import TYPE_CHECKING, Any, Coroutine, Generator

from osmium_protos import (
    PB_ChatPhoto,
    PB_DownloadFilePart,
    PB_FileRef,
    PB_FileRefChatPhotoFileRef,
)

if TYPE_CHECKING:
    from osmium_chat.client import Client


__all__: tuple[str, ...] = ("Photo",)

# 1 MiB per download request.
_DOWNLOAD_CHUNK_SIZE: int = 1024 * 1024


class _PhotoDownload:
    """Awaitable returned by :meth:`Photo.download`.

    Supports both ``data = await photo.download()`` and
    ``async with photo.download() as data:``; in either form the result is the
    full photo :class:`bytes`.
    """

    __slots__: tuple[str, ...] = ("_coro",)

    def __init__(self, coro: "Coroutine[Any, Any, bytes]") -> None:
        self._coro = coro

    def __await__(self) -> "Generator[Any, None, bytes]":
        return self._coro.__await__()

    async def __aenter__(self) -> bytes:
        return await self._coro

    async def __aexit__(self, *exc: object) -> None:
        return None


class Photo:
    """A chat photo: its file id and an inline preview blob."""

    __slots__: tuple[str, ...] = (
        "file_id",
        "preview",
        "_client",
    )

    def __init__(self, photo: PB_ChatPhoto, client: "Client") -> None:
        """Build a photo from a protobuf payload.

        :param photo: The raw ``PB_ChatPhoto`` to read fields from.
        :param client: The client used to download the photo.
        """
        self.file_id: int = photo.file_id
        self.preview: bytes = photo.preview
        self._client = client

    def download(self) -> _PhotoDownload:
        """Fetch the full photo contents as :class:`bytes`.

        The return value can be awaited directly or used as an async context
        manager; both yield the complete photo bytes::

            data = await photo.download()

            async with photo.download() as data:
                ...

        :returns: An awaitable / async context manager resolving to the bytes.
        :raises RequestError: If the gateway rejects any part request.
        """
        return _PhotoDownload(self._download())

    async def _download(self) -> bytes:
        """Request the photo in :data:`_DOWNLOAD_CHUNK_SIZE`-byte windows and
        reassemble them in order, stopping once a short or empty part signals
        the end of the file.
        """
        file_ref = PB_FileRef(
            chat_photo=PB_FileRefChatPhotoFileRef(file_id=self.file_id)
        )
        chunks: list[bytes] = []
        offset = 0
        while True:
            result = await self._client.request(
                PB_DownloadFilePart(
                    file_ref=file_ref,
                    offset=offset,
                    length=_DOWNLOAD_CHUNK_SIZE,
                )
            )
            part = result.file_part
            if part is None or not part.data:
                break
            chunks.append(part.data)
            offset += len(part.data)
            if len(part.data) < _DOWNLOAD_CHUNK_SIZE:
                break
        return b"".join(chunks)
