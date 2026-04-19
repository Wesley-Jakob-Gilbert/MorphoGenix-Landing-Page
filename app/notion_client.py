"""Minimal Notion API client for writing waitlist signups.

Keeps the dependency surface tiny (just httpx) and is easy to swap out later.
"""
from __future__ import annotations

import os
from typing import Optional

import httpx

NOTION_API_URL = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"


class NotionError(Exception):
    """Raised when the Notion API returns an error."""


async def add_waitlist_signup(
    *,
    email: str,
    name: Optional[str] = None,
    reason: Optional[str] = None,
    persona: Optional[str] = None,
    source: str = "Landing Page",
) -> dict:
    """Append a new signup row to the MorphoGenix Beta Waitlist database.

    Requires NOTION_TOKEN and NOTION_DATABASE_ID in the environment.
    """
    token = os.environ.get("NOTION_TOKEN")
    database_id = os.environ.get("NOTION_DATABASE_ID")

    if not token or not database_id:
        raise NotionError(
            "NOTION_TOKEN and NOTION_DATABASE_ID must be set in the environment."
        )

    properties: dict = {
        # Title column is "Email"
        "Email": {"title": [{"text": {"content": email}}]},
        "Source": {"select": {"name": source}},
        "Status": {"status": {"name": "Not started"}},
    }
    if name:
        properties["Name"] = {"rich_text": [{"text": {"content": name}}]}
    if reason:
        properties["Reason for Interest"] = {
            "rich_text": [{"text": {"content": reason}}]
        }
    if persona:
        properties["Persona"] = {"select": {"name": persona}}

    payload = {
        "parent": {"database_id": database_id},
        "properties": properties,
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(NOTION_API_URL, headers=headers, json=payload)

    if resp.status_code >= 300:
        raise NotionError(
            f"Notion API error {resp.status_code}: {resp.text[:400]}"
        )

    return resp.json()
