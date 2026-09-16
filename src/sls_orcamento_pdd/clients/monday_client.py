import random
import time

import requests

from ..utils.logging import emit

ITEM_FIELDS = """
id name created_at updated_at state group { id }
column_values {
  id text value type
  ... on BoardRelationValue { display_value }
  ... on MirrorValue { display_value }
}
"""


class MondayError(RuntimeError):
    pass


class MondayClient:
    def __init__(self, settings, session=None, sleep=time.sleep):
        self.settings = settings
        self.session = session or requests.Session()
        self.sleep = sleep
        self.calls = 0
        self.pages_items = 0
        self.pages_logs = 0
        self.session.headers.update(
            {
                "Authorization": settings.monday_api_token.get_secret_value(),
                "API-Version": settings.monday_api_version,
                "Content-Type": "application/json",
            }
        )

    def query(self, query, variables=None):
        if not self.settings.monday_api_token.get_secret_value():
            raise MondayError("Configure MONDAY_API_TOKEN via Secret Manager/ambiente")
        for attempt in range(self.settings.monday_max_retries + 1):
            delay = min(2**attempt, 60) + random.random()
            try:
                self.calls += 1
                response = self.session.post(
                    self.settings.monday_api_url,
                    json={"query": query, "variables": variables or {}},
                    timeout=self.settings.monday_timeout_seconds,
                )
            except (requests.Timeout, requests.ConnectionError):
                if attempt == self.settings.monday_max_retries:
                    raise MondayError("Monday indisponível após tentativas de conexão") from None
            else:
                try:
                    body = response.json()
                except ValueError:
                    body = {}
                errors = body.get("errors") or []
                codes = {str(e.get("extensions", {}).get("code", "")) for e in errors}
                retryable = response.status_code in (429, 500, 502, 503, 504) or bool(
                    codes
                    & {
                        "COMPLEXITY_BUDGET_EXHAUSTED",
                        "ComplexityException",
                        "RATE_LIMIT_EXCEEDED",
                        "IP_RATE_LIMIT_EXCEEDED",
                        "maxConcurrencyExceeded",
                        "MAX_CONCURRENCY_EXCEEDED",
                    }
                )
                for error in errors:
                    retry = error.get("extensions", {}).get("retry_in_seconds")
                    retry = retry or error.get("retry_in_seconds")
                    if retry:
                        retryable = True
                        delay = max(delay, float(retry))
                if response.headers.get("Retry-After", "").isdigit():
                    delay = max(delay, float(response.headers["Retry-After"]))
                if response.ok and not errors and body.get("data") is not None:
                    return body["data"]
                if not retryable or attempt == self.settings.monday_max_retries:
                    # Never print response payloads, request headers or secrets.
                    raise MondayError(f"Monday HTTP {response.status_code}; codes={sorted(codes)}")
            emit("api_retry", attempt=attempt + 1, wait_seconds=round(delay, 2))
            self.sleep(delay)
        raise MondayError("Tentativas esgotadas")

    def board(self):
        data = self.query(
            """query ($ids: [ID!]!) {
          boards(ids: $ids) { id name items_count created_at
            columns { id title type settings_str }
          }
        }""",
            {"ids": [str(self.settings.monday_board_id)]},
        )
        if len(data.get("boards", [])) != 1:
            raise MondayError("Board inexistente ou token sem permissão")
        return data["boards"][0]

    def item_pages(self):
        cursor = None
        seen = set()
        while True:
            if cursor:
                query = (
                    "query ($cursor: String!, $limit: Int!) { next_items_page(cursor: $cursor, limit: $limit) { cursor items { "
                    + ITEM_FIELDS
                    + " } } }"
                )
                data = self.query(
                    query, {"cursor": cursor, "limit": self.settings.monday_page_size}
                )
                page = data["next_items_page"]
            else:
                query = (
                    "query ($ids: [ID!]!, $limit: Int!) { boards(ids: $ids) { items_page(limit: $limit) { cursor items { "
                    + ITEM_FIELDS
                    + " } } } }"
                )
                data = self.query(
                    query,
                    {
                        "ids": [str(self.settings.monday_board_id)],
                        "limit": self.settings.monday_page_size,
                    },
                )
                page = data["boards"][0]["items_page"]
            self.pages_items += 1
            yield page["items"]
            cursor = page.get("cursor")
            if not cursor:
                break
            if cursor in seen:
                raise MondayError("Cursor repetido; carga abortada para evitar truncamento")
            seen.add(cursor)

    def activity_page(self, page, start, end):
        data = self.query(
            """query ($ids: [ID!]!, $columns: [String], $limit: Int!,
                              $page: Int!, $from: ISO8601DateTime!, $to: ISO8601DateTime!) {
          boards(ids: $ids) { activity_logs(column_ids: $columns, limit: $limit,
            page: $page, from: $from, to: $to) { id event data created_at user_id } }
        }""",
            {
                "ids": [str(self.settings.monday_board_id)],
                "columns": [self.settings.monday_status_column_id],
                "limit": self.settings.monday_log_page_size,
                "page": page,
                "from": start,
                "to": end,
            },
        )
        self.pages_logs += 1
        return data["boards"][0]["activity_logs"]

    def users(self, ids):
        result = []
        values = sorted(set(str(i) for i in ids))
        for start in range(0, len(values), 100):
            data = self.query(
                "query ($ids: [ID!]) { users(ids: $ids) { id name email } }",
                {"ids": values[start : start + 100]},
            )
            result.extend(data["users"])
        return result
