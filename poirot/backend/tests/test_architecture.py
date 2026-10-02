"""Keep application dependencies out of the reusable agent layer."""
import ast
from pathlib import Path


def test_agents_do_not_import_application_layer():
    agents = Path(__file__).resolve().parents[1] / "agents"
    violations = []
    for path in agents.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            if any(name == "poirot.backend.app" or name.startswith("poirot.backend.app.") for name in names):
                violations.append(f"{path.name}:{node.lineno}")
    assert not violations, violations
