import json
import subprocess

from knowledge_os.whatsapp_delivery import (
    PreparedMessage,
    build_sender_args,
    load_recipients,
    parse_user_ids,
    prepare_messages,
    send_message,
    write_delivery_state,
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
    assert messages[0].website_url == "https://www.bvaibhav.info/knos-digest?p=ux"
    assert "Pure design story" in messages[0].message
    assert not messages[0].skipped


def test_prepare_messages_pins_dated_digest_link(tmp_path):
    users_dir = tmp_path / "users"
    users_dir.mkdir()
    _write_user(users_dir / "kintu.json", "kintu", ["ux_design"])
    # Canonical artifact name (YYYY-MM-DD.md) should pin the link to that day.
    digest_path = tmp_path / "2026-05-29.md"
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

    assert messages[0].website_url == (
        "https://www.bvaibhav.info/knos-digest?p=ux&d=2026-05-29"
    )
    assert "d=2026-05-29" in messages[0].message


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
    assert "Quiet one today" in messages[0].message
    assert "Back tomorrow" in messages[0].message


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


def test_send_message_returns_sender_receipt(monkeypatch, capsys):
    prepared = PreparedMessage(
        user_id="vb",
        phone="+15551234567",
        digest_path="knos-digest/2026-06-22.md",
        website_url="https://example.com",
        item_count=1,
        message="hello",
    )
    payload = {
        "ok": True,
        "messageId": "message-1",
        "sentAt": "2026-06-22T08:30:02Z",
        "receiptAt": "2026-06-22T08:30:03Z",
        "receiptStatus": "delivery_ack",
    }

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess([], 0, stdout=json.dumps(payload) + "\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = send_message("sender", prepared)

    assert result == payload
    assert '"receiptStatus": "delivery_ack"' in capsys.readouterr().out


def test_write_delivery_state_is_user_and_digest_scoped(tmp_path):
    path = write_delivery_state(str(tmp_path), "2026-06-22", {
        "user": "vb",
        "status": "delivered",
        "sent_at": "2026-06-22T08:30:02Z",
    })

    assert path.name == "delivery-2026-06-22-vb.json"
    assert json.loads(path.read_text())["status"] == "delivered"
