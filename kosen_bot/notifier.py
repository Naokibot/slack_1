from __future__ import annotations

import logging
import time

from slack_sdk.errors import SlackApiError
from slack_sdk.web import WebClient

LOGGER = logging.getLogger(__name__)


class SlackNotifier:
    def __init__(self, client: WebClient):
        self.client = client

    def post(self, channel_id: str, text: str) -> None:
        if not channel_id:
            LOGGER.warning("Slack post skipped because channel ID is not configured")
            return
        for attempt in range(2):
            try:
                self.client.chat_postMessage(channel=channel_id, text=text)
                return
            except SlackApiError as exc:
                response = exc.response
                if response.status_code == 429 and attempt == 0:
                    retry_after = int(response.headers.get("Retry-After", "1"))
                    LOGGER.warning("Slack rate limited; retrying after %ss", retry_after)
                    time.sleep(max(1, retry_after))
                    continue
                raise
