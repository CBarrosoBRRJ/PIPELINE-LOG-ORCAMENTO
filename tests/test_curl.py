from types import SimpleNamespace

from sls_orcamento_pdd.clients.curl_session import CurlSession


def test_native_transport_utf8_retry_header_and_secret_stdin(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "curl")
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout='HTTP/1.1 429 Too Many Requests\nRetry-After: 12\n\n{"nome":"Orçamento"}\n429',
        )

    monkeypatch.setattr("subprocess.run", fake_run)
    session = CurlSession()
    session.headers["Authorization"] = "secret-test-token"
    result = session.post("https://api.monday.com/v2", json={"query": "{ boards { id } }"})
    assert result.json()["nome"] == "Orçamento"
    assert result.headers["Retry-After"] == "12"
    assert "secret-test-token" not in " ".join(calls[0][0])
    assert "secret-test-token" in calls[0][1]["input"]
