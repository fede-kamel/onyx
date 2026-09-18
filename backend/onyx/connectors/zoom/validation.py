"""Live checks run once, at connector creation, with an admin waiting on the
result. Each mechanism calls what its crawl will call, on the first value it
has, so a missing scope or add-on fails here instead of on the first indexing
attempt. Whether an ID or email is right is discovery's job, and it reports
every bad one as an indexing error.
"""

from collections.abc import Callable
from datetime import date
from typing import TypeVar

import requests

from onyx.connectors.exceptions import (
    ConnectorValidationError,
    UnexpectedValidationError,
    ValidationError,
)
from onyx.connectors.zoom.client import ZoomClient
from onyx.connectors.zoom.recordings.discovery import session_ids

_T = TypeVar("_T")


def _configured(values: list[str] | None) -> list[str]:
    return [value.strip() for value in values or [] if value and value.strip()]


def _probe(description: str, call: Callable[[], _T]) -> _T:
    """A 503 or a dropped connection must not become ConnectorValidationError,
    because that would disable the connector over a Zoom outage."""
    try:
        return call()
    except ValidationError:
        raise
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else None
        if status == 404:
            raise ConnectorValidationError(
                f"Zoom has no {description}. Check the value; Zoom may also have "
                "deleted it, or it may be past Zoom's retention window."
            ) from e
        if status == 400:
            raise ConnectorValidationError(f"Zoom refused {description}: {e}") from e
        raise UnexpectedValidationError(
            f"Zoom answered {status} while checking {description}: {e}"
        ) from e
    except requests.RequestException as e:
        raise UnexpectedValidationError(
            f"Could not reach Zoom while checking {description}: {e}"
        ) from e


def _probe_transcript_scope(client: ZoomClient, uuid: str) -> None:
    """Every path reads transcripts through this endpoint. A 404 only means the
    sample session was never cloud-recorded, which says nothing about scopes."""

    def read() -> None:
        try:
            client.get_transcript(uuid)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return
            raise

    _probe(f"the recording files of {uuid}", read)


def probe_zoom(
    client: ZoomClient,
    *,
    meeting_ids: list[str] | None,
    webinar_ids: list[str] | None,
    host_emails: list[str] | None,
    group_id: str | None,
) -> None:
    meeting_ids = session_ids(meeting_ids)
    webinar_ids = session_ids(webinar_ids)
    host_emails = _configured(host_emails)
    group_id = group_id.strip() if group_id and group_id.strip() else None

    _probe("the OAuth token request", client.check_credentials)

    sample_uuid: str | None = None
    if meeting_ids:
        first_meeting = meeting_ids[0]
        occurrences = _probe(
            f"meeting {first_meeting}",
            lambda: client.list_past_meeting_occurrences(first_meeting),
        )
        sample_uuid = sample_uuid or next((o.uuid for o in occurrences), None)
    if webinar_ids:
        first_webinar = webinar_ids[0]
        occurrences = _probe(
            f"webinar {first_webinar}",
            lambda: client.list_past_webinar_occurrences(first_webinar),
        )
        sample_uuid = sample_uuid or next((o.uuid for o in occurrences), None)

    sample_user: str | None = None
    if host_emails:
        page = _probe("the account's users", client.list_users)
        sample_user = next((u.id for u in page.users if u.id), None)
    if group_id:
        members = _probe(
            f"Zoom Group {group_id}", lambda: client.list_group_members(group_id)
        )
        sample_user = next((u.id for u in members.users if u.id), None) or sample_user

    if sample_user:
        user_id = sample_user
        today = date.today()
        recordings = _probe(
            f"the recordings of user {user_id}",
            lambda: client.list_user_recordings(user_id, today, today),
        )
        sample_uuid = sample_uuid or next((r.uuid for r in recordings.recordings), None)

    if sample_uuid:
        _probe_transcript_scope(client, sample_uuid)
