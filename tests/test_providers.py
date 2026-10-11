from __future__ import annotations

import json
import threading
import time
from types import SimpleNamespace

from congressional_globe import providers


def test_ollama_requests_from_separate_providers_are_serialized(monkeypatch) -> None:
    state = {"active": 0, "maximum": 0}
    guard = threading.Lock()

    class FakeClient:
        def __init__(self, **_kwargs) -> None:
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **_kwargs):
            with guard:
                state["active"] += 1
                state["maximum"] = max(state["maximum"], state["active"])
            time.sleep(0.03)
            with guard:
                state["active"] -= 1
            message = SimpleNamespace(
                content=json.dumps(
                    {"edits": [], "needs_image_review": False, "review_reason": None}
                )
            )
            return SimpleNamespace(
                choices=[SimpleNamespace(message=message, finish_reason="stop")], usage=None
            )

    monkeypatch.setattr(providers, "OpenAI", FakeClient)
    first = providers.OllamaProvider("model-a", "http://local")
    second = providers.OllamaProvider("model-b", "http://local")
    threads = [
        threading.Thread(target=provider.clean, args=("text",)) for provider in (first, second)
    ]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert state["maximum"] == 1
