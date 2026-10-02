"""Build and smoke-test a wheel away from the checkout (no editable import leaks).

Run with the project's development Python: python scripts/check_wheel.py
Build dependencies may be downloaded; runtime dependencies must already exist.
"""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile


def run(*args: str, cwd: Path) -> None:
    subprocess.run([sys.executable, *args], cwd=cwd, check=True)


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="poirot-wheel-") as directory:
        root = Path(directory)
        source = root / "source"
        source.mkdir()
        for name in ("pyproject.toml", "LICENSE", "THIRD_PARTY_LICENSES.md"):
            shutil.copy2(repository / name, source / name)
        shutil.copytree(repository / "poirot", source / "poirot",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        wheels = root / "wheels"
        run("-m", "pip", "wheel", ".", "--no-deps", "--disable-pip-version-check",
            "--wheel-dir", str(wheels), cwd=source)
        wheel, = wheels.glob("*.whl")
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            required = (
                "poirot/backend/agents/prompts/system/leader/identity.md",
                "poirot/backend/agents/config/profiles/general.yaml",
                "poirot/backend/agents/skill/builtin_skills/core/bootstrap/SKILL.md",
                "poirot/backend/agents/multiagent/extensions/pi-sandbox-bridge/index.ts",
            )
            for name in required:
                assert name in names, f"wheel missing {name}"
            assert not any("/tests/" in name for name in names), "wheel includes test packages"
            # Check every tracked runtime asset, not just representative filenames.
            agents = source / "poirot/backend/agents"
            for pattern in ("prompts/**/*.md", "config/profiles/*.yaml",
                            "skill/builtin_skills/**/SKILL.md", "multiagent/extensions/**/*.ts"):
                for asset in agents.glob(pattern):
                    assert asset.relative_to(source).as_posix() in names, f"missing asset: {asset}"
        installed = root / "installed"
        run("-m", "pip", "install", "--no-deps", "--target", str(installed), str(wheel), cwd=root)
        smoke = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from poirot.backend.agents.prompts.manager import get_prompt_manager
from poirot.backend.agents.leader.factory import make_lead_agent
from poirot.backend.agents.capabilities.registry import CapabilityRegistry
from langchain_core.language_models.fake_chat_models import FakeListChatModel
class Model(FakeListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self
assert get_prompt_manager().load('leader', 'identity').strip()
model = Model(responses=['ok'])
agent = make_lead_agent(capability_registry=CapabilityRegistry(models={'researcher': model, 'reporter': model}))
assert agent.graph is not None
assert not (Path(sys.argv[1]) / 'poirot/backend/tests').exists()
print('Installed wheel: resources present, graph construction succeeded, tests excluded.')
"""
        run("-I", "-c", smoke, str(installed), cwd=root)


if __name__ == "__main__":
    main()
