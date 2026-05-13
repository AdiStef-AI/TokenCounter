"""Anthropic Admin API usage/cost endpoints.

Requires an Admin API key (sk-ant-admin...) and an organization account.
Individual accounts cannot use these endpoints.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import anthropic


class AdminAPIUnavailable(Exception):
    """Raised when Admin API key is not configured."""


def _get_admin_client(admin_key: str | None = None) -> anthropic.Anthropic:
    key = admin_key or os.environ.get("ANTHROPIC_ADMIN_KEY")
    if not key:
        raise AdminAPIUnavailable(
            "No Admin API key found. Set ANTHROPIC_ADMIN_KEY environment variable.\n"
            "Admin keys start with 'sk-ant-admin' and require an organization account."
        )
    return anthropic.Anthropic(api_key=key)


def fetch_usage_report(
    days: int = 7,
    bucket_width: str = "1d",
    group_by: list[str] | None = None,
    admin_key: str | None = None,
) -> dict[str, Any]:
    """Fetch usage report from Anthropic Admin API.

    bucket_width: "1m", "1h", or "1d"
    group_by: list of dimensions e.g. ["model", "workspace_id"]
    """
    import httpx

    key = admin_key or os.environ.get("ANTHROPIC_ADMIN_KEY")
    if not key:
        raise AdminAPIUnavailable(
            "No Admin API key found. Set ANTHROPIC_ADMIN_KEY environment variable."
        )

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    params: dict[str, Any] = {
        "starting_at": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ending_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bucket_width": bucket_width,
    }

    if group_by:
        for dim in group_by:
            params.setdefault("group_by[]", [])
            if isinstance(params["group_by[]"], list):
                params["group_by[]"].append(dim)

    headers = {
        "anthropic-version": "2023-06-01",
        "x-api-key": key,
    }

    with httpx.Client() as client:
        resp = client.get(
            "https://api.anthropic.com/v1/organizations/usage_report/messages",
            params=params,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


def fetch_cost_report(
    days: int = 30,
    group_by: list[str] | None = None,
    admin_key: str | None = None,
) -> dict[str, Any]:
    """Fetch cost report from Anthropic Admin API (daily granularity only)."""
    import httpx

    key = admin_key or os.environ.get("ANTHROPIC_ADMIN_KEY")
    if not key:
        raise AdminAPIUnavailable(
            "No Admin API key found. Set ANTHROPIC_ADMIN_KEY environment variable."
        )

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    params: dict[str, Any] = {
        "starting_at": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ending_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bucket_width": "1d",
    }

    if group_by:
        for dim in group_by:
            params.setdefault("group_by[]", [])
            if isinstance(params["group_by[]"], list):
                params["group_by[]"].append(dim)

    headers = {
        "anthropic-version": "2023-06-01",
        "x-api-key": key,
    }

    with httpx.Client() as client:
        resp = client.get(
            "https://api.anthropic.com/v1/organizations/cost_report",
            params=params,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
