"""The Researcher can read web pages, but never private or local addresses."""

import asyncio

import httpx
import pytest

from fakes import ScriptedModel, tool_call, tool_results
from strands_assistant import agent as agent_module
from strands_assistant.web import PublicOnlyTransport, make_public_web_client

PUBLIC_IP = "93.184.216.34"


def _resolver(mapping: dict[str, list[str]]):
    async def resolve(host: str, port: int) -> list[str]:
        return mapping.get(host, [PUBLIC_IP])

    return resolve


class Recorder:
    """An inner transport that records what actually went out, and serves one page or a redirect."""

    def __init__(self, redirect_to: str | None = None) -> None:
        self.urls: list[str] = []
        self.redirect_to = redirect_to

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.urls.append(str(request.url))
        if self.redirect_to:
            return httpx.Response(302, headers={"location": self.redirect_to})
        return httpx.Response(200, html="<h1>Hello</h1><p>The page says hello.</p>")


def _get(url: str, recorder: Recorder, mapping: dict[str, list[str]] | None = None) -> httpx.Response:
    transport = PublicOnlyTransport(inner=httpx.MockTransport(recorder), resolve=_resolver(mapping or {}))

    async def go():
        async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
            return await client.get(url)

    return asyncio.run(go())


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:11434/api/tags",
        "http://10.0.0.5/",
        "http://192.168.1.1/admin",
        "http://172.16.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://0.0.0.0:8000/",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
    ],
)
def test_private_and_local_ip_addresses_are_refused(url):
    recorder = Recorder()

    with pytest.raises(httpx.ConnectError, match="private"):
        _get(url, recorder)

    assert recorder.urls == []


def test_a_name_that_resolves_to_a_private_address_is_refused():
    recorder = Recorder()

    with pytest.raises(httpx.ConnectError, match="private"):
        _get("http://sneaky.example/", recorder, {"sneaky.example": [PUBLIC_IP, "127.0.0.1"]})

    assert recorder.urls == []


def test_a_redirect_to_a_private_address_is_refused():
    recorder = Recorder(redirect_to="http://127.0.0.1:11434/api/tags")

    with pytest.raises(httpx.ConnectError, match="private"):
        _get("https://public.example/", recorder)

    assert recorder.urls == ["https://public.example/"]


def test_public_addresses_go_through():
    recorder = Recorder()

    response = _get("https://public.example/page", recorder)

    assert response.status_code == 200
    assert recorder.urls == ["https://public.example/page"]


def test_localhost_is_refused_with_the_real_resolver():
    async def go():
        async with make_public_web_client() as client:
            await client.get("http://localhost:11434/api/tags")

    with pytest.raises(httpx.ConnectError, match="private"):
        asyncio.run(go())


@pytest.fixture
def scripted(monkeypatch):
    monkeypatch.delenv("CLOUD_MODE", raising=False)
    models: dict[str, ScriptedModel] = {}

    def fake_build_model(priority_env: str, default: str = "") -> ScriptedModel:
        return models.setdefault(priority_env, ScriptedModel())

    monkeypatch.setattr(agent_module, "build_model", fake_build_model)
    return models


def test_the_researcher_can_summarize_a_page(scripted, monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(
        agent_module,
        "make_public_web_client",
        lambda: httpx.AsyncClient(
            transport=PublicOnlyTransport(inner=httpx.MockTransport(recorder), resolve=_resolver({})),
            follow_redirects=True,
        ),
    )
    model = ScriptedModel(
        [
            tool_call("web_fetch", {"url": "https://public.example/page", "prompt": "What does it say?"}),
            "The page says hello.",  # the analyst's answer
            "Summary: the page says hello. Source: https://public.example/page",
        ]
    )
    scripted["RESEARCHER_MODEL_PRIORITY"] = model

    researcher = agent_module.create_researcher()
    researcher("summarize https://public.example/page")

    assert recorder.urls == ["https://public.example/page"]
    assert "The page says hello." in str(model.requests[1]["messages"])  # the analyst saw the page
    assert "The page says hello." in tool_results(researcher.messages)[-1]


def test_the_researcher_refuses_to_fetch_localhost(scripted):
    scripted["RESEARCHER_MODEL_PRIORITY"] = ScriptedModel(
        [tool_call("web_fetch", {"url": "http://localhost:11434/api/tags", "prompt": "list models"}), "ok"]
    )

    researcher = agent_module.create_researcher()
    researcher("what models are on localhost?")

    assert "private" in tool_results(researcher.messages)[-1]
