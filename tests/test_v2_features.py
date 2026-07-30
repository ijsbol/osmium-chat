import asyncio
from types import SimpleNamespace

from osmium_chat import (
    Bot,
    Button,
    Channel,
    ChannelType,
    MessageCloak,
    MessageQuote,
    User,
)
from osmium_chat.file import FileMetadata
from osmium_chat.message import Message
from osmium_protos import (
    PB_ChatPhoto,
    PB_ChatRef,
    PB_Channel,
    PB_ChannelRef,
    PB_FileMetadata,
    PB_FileMetadataMetadataFile,
    PB_FileMetadataMetadataImage,
    PB_Message,
    PB_MessageMedia,
    PB_MessageMessageBotInfo,
    PB_MessageMessageBotInfoMessageCloak,
    PB_MessageMessageForwardInfo,
    PB_MessageMessageReplyInfo,
    PB_MessageMessageReplyInfoQuote,
    PB_MediaEmbed,
    PB_RpcResult,
    PB_SentMessage,
    PB_UpdateInteraction,
    PB_UserRef,
)


class FakeClient:
    def __init__(self) -> None:
        self.bot = SimpleNamespace(user=None)
        self.requests = []

    async def request(self, payload):
        self.requests.append(payload)
        return PB_RpcResult(sent_message=PB_SentMessage(message_id=99))


def test_media_metadata_preserves_empty_oneofs() -> None:
    image = FileMetadata(PB_FileMetadata(image=PB_FileMetadataMetadataImage()))
    generic = FileMetadata(PB_FileMetadata(file=PB_FileMetadataMetadataFile()))
    assert image.kind == "image"
    assert image.image is not None
    assert generic.kind == "file"
    assert generic.file is not None


def test_message_parses_v2_metadata() -> None:
    client = FakeClient()
    message = Message(
        PB_Message(
            message_id=1,
            author_id=2,
            message="hello",
            chat_ref=PB_ChatRef(user=PB_UserRef(user_id=3)),
            reply=PB_MessageMessageReplyInfo(
                message_id=4,
                quote=PB_MessageMessageReplyInfoQuote(message="quoted", offset=1),
            ),
            forward=PB_MessageMessageForwardInfo(date=123),
            bot_info=PB_MessageMessageBotInfo(
                cloak=PB_MessageMessageBotInfoMessageCloak(
                    name="Alias",
                    photo=PB_ChatPhoto(file_id=8),
                ),
            ),
            media=[PB_MessageMedia(embed=PB_MediaEmbed(url="https://example.test"))],
        ),
        client,
    )
    assert message.reply_to == 4
    assert message.reply_quote is not None
    assert message.reply_quote.message == "quoted"
    assert message.forward_info is not None
    assert message.forward_info.date == 123
    assert message.cloak == MessageCloak("Alias", 8)
    assert message.is_cloaked
    assert message.true_author_id == 2
    assert message.embeds[0].url == "https://example.test"


def test_channel_send_serializes_rich_options() -> None:
    async def run() -> None:
        client = FakeClient()
        channel = Channel(
            PB_ChatRef(user=PB_UserRef(user_id=3)),
            client,
        )
        button = Button("Click", "fixed")
        await channel.send(
            "hello",
            reply_to=7,
            quote=MessageQuote("quoted", offset=2),
            suppress_embeds=True,
            cloak=MessageCloak("Alias", 8),
            buttons=[[button]],
            client_id=11,
        )
        request = client.requests[0]
        assert request.reply_to.message_id == 7
        assert request.reply_to.quote.offset == 2
        assert request.suppress_embeds
        assert request.bot_info.cloak.name == "Alias"
        assert request.bot_info.buttons.rows[0].buttons[0].interaction.data == "fixed"
        assert request.client_id == 11

    asyncio.run(run())


def test_button_routing_prefers_instance_callback() -> None:
    async def run() -> None:
        bot = Bot("!", 1)
        calls = []

        class TestButton(Button):
            async def on_interaction(self, interaction) -> None:
                calls.append(("button", interaction.data))

        button = TestButton("Click")
        bot._client.register_buttons(42, [[button]])

        async def global_handler(interaction) -> None:
            calls.append(("global", interaction.data))

        bot._listeners["interaction"] = [global_handler]
        await bot.process_interaction(PB_UpdateInteraction(
            interaction_id=1,
            user_id=2,
            message_id=42,
            data=button.custom_id,
        ))
        await bot.process_interaction(PB_UpdateInteraction(
            interaction_id=2,
            user_id=2,
            message_id=43,
            data="unknown",
        ))
        assert calls[0] == ("button", button.custom_id)
        assert calls[1] == ("global", "unknown")

    asyncio.run(run())


def test_channel_metadata_from_proto() -> None:
    channel = Channel.from_pb(
        PB_Channel(
            id=1,
            community_id=2,
            name="news",
            type=ChannelType.ANNOUNCEMENT,
            position=0,
            flags=1,
            highlighted_msg_id=8,
            description="Updates",
            slowmode_seconds=30,
        ),
        FakeClient(),
    )
    assert channel.type is ChannelType.ANNOUNCEMENT
    assert channel.description == "Updates"
    assert channel.slowmode_seconds == 30
    assert channel.highlighted_message_id == 8


def test_channel_edit_serializes_new_metadata() -> None:
    async def run() -> None:
        client = FakeClient()
        channel = Channel.from_pb(
            PB_Channel(
                id=1,
                community_id=2,
                name="news",
                type=ChannelType.TEXT,
                position=0,
            ),
            client,
        )
        await channel.edit(
            description="Updates",
            slowmode_seconds=15,
            highlighted_message_id=8,
        )
        request = client.requests[0]
        assert request.description == "Updates"
        assert request.slowmode_seconds == 15
        assert request.highlighted_msg_id.highlighted_msg_id == 8
        assert channel.description == "Updates"

    asyncio.run(run())
