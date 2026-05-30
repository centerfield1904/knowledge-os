import json

from knowledge_os.whatsapp_delivery import (
    build_sender_args,
    load_recipients,
    parse_user_ids,
    prepare_messages,
)


def _write_user(path, user_id, personas):
    path.write_text(json.dumps({
        "user": {"identifier": user_id, "personas": personas},
        "delivery": {"base_url": "https://www.bvaibhav.info/knos-digest"},
    }))


def test_prepare_messages_builds_persona_website_message(tmp_path):
    users_dir = tmp_path / "users"
    users_dir.mkdir()
    _write_user(users_dir / "kintu.json", "kintu", ["ux_design"])
    digest_path = tmp_path / "digest.md"
    digest_path.write_text(
        "\n".join([
            "*Knowledge Digest*",
            "",
            "<!-- knos-persona: ux_design | UX / Design -->",
            "## UX / Design",
            "",
            "*UX / Design*",
            "- [ ] Pure design story",
            "  https://example.com/story",
            "",
        ])
    )

    messages = prepare_messages(
        user_ids=["kintu"],
        recipients={"kintu": "+15551234567"},
        digest_path=str(digest_path),
        users_dir=str(users_dir),
    )

    assert len(messages) == 1
    assert messages[0].user_id == "kintu"
    assert messages[0].phone == "+15551234567"
    assert messages[0].item_count == 1
    assert messages[0].website_url == "https://www.bvaibhav.info/knos-digest?personas=ux_design"
    assert "Pure design story" in messages[0].message
    assert not messages[0].skipped


def test_prepare_messages_sends_zero_item_focus_message(tmp_path):
    users_dir = tmp_path / "users"
    users_dir.mkdir()
    _write_user(users_dir / "mikey.json", "mikey", ["ai_researcher"])
    digest_path = tmp_path / "digest.md"
    digest_path.write_text("*Knowledge Digest*\n")

    messages = prepare_messages(
        user_ids=["mikey"],
        recipients={"mikey": "+15557654321"},
        digest_path=str(digest_path),
        users_dir=str(users_dir),
    )

    assert messages[0].item_count == 0
    assert not messages[0].skipped
    assert "Nothing worth noticing surfaced" in messages[0].message
    assert "stay focused" in messages[0].message


def test_prepare_messages_can_skip_zero_item_users(tmp_path):
    users_dir = tmp_path / "users"
    users_dir.mkdir()
    _write_user(users_dir / "mikey.json", "mikey", ["ai_researcher"])
    digest_path = tmp_path / "digest.md"
    digest_path.write_text("*Knowledge Digest*\n")

    messages = prepare_messages(
        user_ids=["mikey"],
        recipients={"mikey": "+15557654321"},
        digest_path=str(digest_path),
        users_dir=str(users_dir),
        skip_empty=True,
    )

    assert messages[0].item_count == 0
    assert messages[0].skipped


def test_load_recipients_and_parse_users(tmp_path):
    path = tmp_path / "recipients.json"
    path.write_text(json.dumps({"vb": " +910000000000 ", "mikey": "+15550000000"}))

    assert load_recipients(str(path)) == {"vb": "+910000000000", "mikey": "+15550000000"}
    assert parse_user_ids("mikey,kintu", ["vb", "mikey"]) == ["vb", "mikey", "kintu"]
    assert parse_user_ids(None, ["kintu"]) == ["kintu"]


def test_build_sender_args_supports_default_and_template_shapes():
    assert build_sender_args("node scripts/baileys_send.mjs --to {phone} --message {message}", "+15551234567", "hello") == [
        "node",
        "scripts/baileys_send.mjs",
        "--to",
        "+15551234567",
        "--message",
        "hello",
    ]
    assert build_sender_args("whatsapp-send", "+15551234567", "hello") == [
        "whatsapp-send",
        "--to",
        "+15551234567",
        "--message",
        "hello",
    ]
    assert build_sender_args(
        "whatsapp-send --phone {phone} --text {message}",
        "+15551234567",
        "hello there",
    ) == [
        "whatsapp-send",
        "--phone",
        "+15551234567",
        "--text",
        "hello there",
    ]
