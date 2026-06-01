from osmium_protos import PB_ChatPhoto


__all__: tuple[str, ...] = (
    "Photo",
)


class Photo:
    """A chat photo: its file id and an inline preview blob."""

    __slots__: tuple[str, ...] = (
        "file_id",
        "preview",
    )

    def __init__(self, photo: PB_ChatPhoto) -> None:
        """Build a photo from a protobuf payload.

        :param photo: The raw ``PB_ChatPhoto`` to read fields from.
        """
        self.file_id: int = photo.file_id
        self.preview: bytes = photo.preview
