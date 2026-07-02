"""Polling helper: wait_until_complete (spec §6.9)."""

from __future__ import annotations

import time
from typing import Callable

from smileid.errors import TimeoutError
from smileid.generated.models import JobStatus


def wait_until_complete(
    retrieve: Callable[[str], JobStatus],
    job_id: str,
    *,
    interval: float = 2.0,
    timeout: float = 60.0,
    treat_not_found_as_pending: bool = True,
) -> JobStatus:
    """Poll ``retrieve`` until the job completes (spec §6.9).

    Returns the terminal :class:`JobStatus`. When ``treat_not_found_as_pending``
    is false, a ``not_found`` result is returned immediately. Raises
    :class:`smileid.errors.TimeoutError` if the job does not complete within
    ``timeout`` seconds.
    """
    deadline = time.monotonic() + timeout
    while True:
        status = retrieve(job_id)
        if status.status == "complete":
            return status
        if status.status == "not_found" and not treat_not_found_as_pending:
            return status
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"job {job_id} did not complete within {timeout} seconds"
            )
        time.sleep(interval)
