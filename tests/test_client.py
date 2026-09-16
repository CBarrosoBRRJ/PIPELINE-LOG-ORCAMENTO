import json

import pytest
import requests

from sls_orcamento_ppd.clients.monday_client import MondayClient, MondayError


class Session:
    def __init__(self, responses):
        self.headers = {}
        self.responses = iter(responses)

    def post(self, *args, **kwargs):
        return next(self.responses)


def response(body, code=200):
    r = requests.Response()
    r.status_code = code
    r._content = json.dumps(body).encode()
    return r


def test_http200_graphql_retry(settings):
    waits = []
    c = MondayClient(
        settings,
        Session(
            [
                response(
                    {
                        "errors": [
                            {
                                "extensions": {
                                    "code": "COMPLEXITY_BUDGET_EXHAUSTED",
                                    "retry_in_seconds": 10,
                                }
                            }
                        ]
                    }
                ),
                response({"data": {"ok": True}}),
            ]
        ),
        sleep=waits.append,
    )
    assert c.query("test") == {"ok": True}
    assert waits[0] >= 10


def test_partial_data_rejected_and_credentials_not_in_error(settings):
    c = MondayClient(
        settings,
        Session(
            [
                response(
                    {
                        "data": {"boards": []},
                        "errors": [
                            {"message": "test-only secret", "extensions": {"code": "AccessDenied"}}
                        ],
                    }
                )
            ]
        ),
    )
    with pytest.raises(MondayError) as e:
        c.query("test")
    assert "test-only" not in str(e.value)


def test_cursor_pages_and_repeated_cursor(settings):
    c = MondayClient(
        settings,
        Session(
            [
                response(
                    {"data": {"boards": [{"items_page": {"items": [{"id": "1"}], "cursor": "a"}}]}}
                ),
                response({"data": {"next_items_page": {"items": [{"id": "2"}], "cursor": None}}}),
            ]
        ),
    )
    assert [r[0]["id"] for r in c.item_pages()] == ["1", "2"]
