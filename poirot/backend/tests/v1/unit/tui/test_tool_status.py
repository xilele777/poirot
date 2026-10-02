from types import SimpleNamespace

import pytest

from poirot.backend.app.tui.app import PoirotTUI
from poirot.backend.app.tui.conversation import ConversationLog


@pytest.mark.parametrize("status,marker", [("error", "✗"), ("success", "✓")])
def test_tool_status_is_visible_in_conversation_and_execution_panel(monkeypatch, status, marker):
    event = {"type": "tool_end", "tool_name": "web_search", "tool_result": "result", "tool_status": status}
    log = ConversationLog()
    written = []
    monkeypatch.setattr(log, "write", lambda text: written.append(text.plain))
    log._render_tool_end(event)
    assert written[0].startswith(f"  {marker} web_search")

    updates = []
    app = SimpleNamespace(
        query_one=lambda *args: SimpleNamespace(update=updates.append),
        _flush_steer_queue=lambda: None,
    )
    PoirotTUI._update_exec_panel(app, event)
    assert updates[0].startswith(f"{marker} web_search")
