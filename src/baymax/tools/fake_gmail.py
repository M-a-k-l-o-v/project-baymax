"""Fake Gmail adapter for deterministic eval runs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from baymax.tools.fake_base import FakeToolResult

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class GmailContact(BaseModel):
    """Gmail contact stored in fake state."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    email: str = Field(pattern=EMAIL_PATTERN)


class GmailMessage(BaseModel):
    """Existing Gmail message stored in fake state."""

    model_config = ConfigDict(extra="forbid")

    id: str
    sender_name: str = Field(min_length=1)
    sender_email: str = Field(pattern=EMAIL_PATTERN)
    subject: str = Field(min_length=1)
    received_at: str
    body: str | None = None


class GmailDraft(BaseModel):
    """Gmail draft created by the fake adapter."""

    model_config = ConfigDict(extra="forbid")

    id: str
    recipient: str = Field(pattern=EMAIL_PATTERN)
    body: str = Field(min_length=1)
    subject: str | None = None
    thread_id: str | None = None


class SentEmail(BaseModel):
    """Email sent by the fake adapter."""

    model_config = ConfigDict(extra="forbid")

    id: str
    recipient: str = Field(pattern=EMAIL_PATTERN)
    body: str = Field(min_length=1)
    subject: str | None = None


class FakeGmailAdapter:
    """In-memory Gmail adapter backed by scenario state."""

    def __init__(
        self,
        *,
        contacts: list[GmailContact] | None = None,
        messages: list[GmailMessage] | None = None,
        drafts: list[GmailDraft] | None = None,
        sent_emails: list[SentEmail] | None = None,
    ) -> None:
        self._contacts = list(contacts or [])
        self._messages = list(messages or [])
        self._drafts = list(drafts or [])
        self._sent_emails = list(sent_emails or [])

    @classmethod
    def from_initial_state(cls, initial_state: dict[str, Any]) -> FakeGmailAdapter:
        contacts = [
            GmailContact.model_validate(contact)
            for contact in initial_state.get("gmail_contacts", [])
        ]
        messages = [
            GmailMessage.model_validate(message)
            for message in initial_state.get("gmail_messages", [])
        ]
        drafts = [
            GmailDraft.model_validate(draft)
            for draft in initial_state.get("gmail_drafts", [])
        ]
        sent_emails = [
            SentEmail.model_validate(email)
            for email in initial_state.get("sent_emails", [])
        ]
        return cls(
            contacts=contacts,
            messages=messages,
            drafts=drafts,
            sent_emails=sent_emails,
        )

    def export_state(self) -> dict[str, Any]:
        return {
            "gmail_contacts": [
                contact.model_dump(mode="json") for contact in self._contacts
            ],
            "gmail_messages": [
                message.model_dump(mode="json", exclude_none=True)
                for message in self._messages
            ],
            "gmail_drafts": [
                draft.model_dump(mode="json", exclude_none=True)
                for draft in self._drafts
            ],
            "sent_emails": [
                email.model_dump(mode="json", exclude_none=True)
                for email in self._sent_emails
            ],
        }

    def create_draft(
        self,
        *,
        recipient: str,
        body: str,
        subject: str | None = None,
        thread_id: str | None = None,
    ) -> FakeToolResult:
        draft = GmailDraft(
            id=self._next_draft_id(),
            recipient=recipient,
            body=body,
            subject=subject,
            thread_id=thread_id,
        )
        self._drafts.append(draft)
        return FakeToolResult(
            success=True,
            tool="gmail.create_draft",
            data={"draft_id": draft.id},
        )

    def send_email(
        self,
        *,
        recipient: str,
        body: str,
        subject: str | None = None,
    ) -> FakeToolResult:
        email = SentEmail(
            id=self._next_sent_email_id(),
            recipient=recipient,
            body=body,
            subject=subject,
        )
        self._sent_emails.append(email)
        return FakeToolResult(
            success=True,
            tool="gmail.send_email",
            data={"email_id": email.id},
        )

    def _next_draft_id(self) -> str:
        existing_ids = {draft.id for draft in self._drafts}
        next_index = len(self._drafts) + 1
        while True:
            candidate_id = f"draft_fake_gmail_{next_index:03}"
            if candidate_id not in existing_ids:
                return candidate_id
            next_index += 1

    def _next_sent_email_id(self) -> str:
        existing_ids = {email.id for email in self._sent_emails}
        next_index = len(self._sent_emails) + 1
        while True:
            candidate_id = f"email_fake_gmail_{next_index:03}"
            if candidate_id not in existing_ids:
                return candidate_id
            next_index += 1
