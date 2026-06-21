import pytest
from pydantic import ValidationError

from baymax.tools.fake_gmail import FakeGmailAdapter


def test_create_draft_adds_draft_without_sending_email() -> None:
    adapter = FakeGmailAdapter.from_initial_state(
        {
            "gmail_contacts": [],
            "gmail_drafts": [],
            "sent_emails": [],
        }
    )

    result = adapter.create_draft(
        recipient="maya@example.com",
        body="I will send the notes tonight.",
    )

    state = adapter.export_state()
    assert result.success is True
    assert result.tool == "gmail.create_draft"
    assert result.data == {"draft_id": "draft_fake_gmail_001"}
    assert state["gmail_drafts"] == [
        {
            "id": "draft_fake_gmail_001",
            "recipient": "maya@example.com",
            "body": "I will send the notes tonight.",
        }
    ]
    assert state["sent_emails"] == []


def test_send_email_adds_sent_email_without_creating_draft() -> None:
    adapter = FakeGmailAdapter.from_initial_state(
        {
            "gmail_drafts": [],
            "sent_emails": [],
        }
    )

    result = adapter.send_email(
        recipient="marv@example.com",
        body="I will be 10 minutes late.",
    )

    state = adapter.export_state()
    assert result.success is True
    assert result.tool == "gmail.send_email"
    assert result.data == {"email_id": "email_fake_gmail_001"}
    assert state["gmail_drafts"] == []
    assert state["sent_emails"] == [
        {
            "id": "email_fake_gmail_001",
            "recipient": "marv@example.com",
            "body": "I will be 10 minutes late.",
        }
    ]


def test_create_draft_generates_non_colliding_id() -> None:
    adapter = FakeGmailAdapter.from_initial_state(
        {
            "gmail_drafts": [
                {
                    "id": "draft_fake_gmail_002",
                    "recipient": "maya@example.com",
                    "body": "Existing draft",
                }
            ]
        }
    )

    adapter.create_draft(
        recipient="omar@example.com",
        body="I will send the notes tonight.",
    )

    drafts = adapter.export_state()["gmail_drafts"]
    assert drafts[1]["id"] == "draft_fake_gmail_003"


def test_send_email_generates_non_colliding_id() -> None:
    adapter = FakeGmailAdapter.from_initial_state(
        {
            "sent_emails": [
                {
                    "id": "email_fake_gmail_002",
                    "recipient": "maya@example.com",
                    "body": "Existing sent email",
                }
            ]
        }
    )

    adapter.send_email(
        recipient="omar@example.com",
        body="I will send the notes tonight.",
    )

    sent_emails = adapter.export_state()["sent_emails"]
    assert sent_emails[1]["id"] == "email_fake_gmail_003"


def test_rejects_invalid_email_argument() -> None:
    adapter = FakeGmailAdapter.from_initial_state({})

    with pytest.raises(ValidationError):
        adapter.create_draft(
            recipient="not-an-email",
            body="I will send the notes tonight.",
        )


def test_rejects_invalid_initial_contact() -> None:
    with pytest.raises(ValidationError):
        FakeGmailAdapter.from_initial_state(
            {
                "gmail_contacts": [
                    {
                        "name": "Maya Khan",
                        "email": "not-an-email",
                    }
                ]
            }
        )
