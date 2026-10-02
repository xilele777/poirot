from dataclasses import replace
from unittest.mock import Mock

import pytest

from poirot.backend.agents.multiagent.bootstrap import setup_multiagent
from poirot.backend.agents.multiagent.config import MultiAgentConfig


@pytest.mark.parametrize("layer", ["l2", "l3"])
def test_unavailable_evolution_fails_before_creating_runtime(tmp_path, monkeypatch, layer):
    config = MultiAgentConfig(enabled=True, metrics_db_path=str(tmp_path / "metrics.db"))
    config = replace(config, **{layer: replace(getattr(config, layer), enabled=True)})
    metrics = Mock()
    monkeypatch.setattr("poirot.backend.agents.multiagent.bootstrap.MultiAgentMetricsStore", metrics)
    with pytest.raises(ValueError, match="no configured mutation caller"):
        setup_multiagent(config)
    metrics.assert_not_called()
    assert not (tmp_path / "metrics.db").exists()


def test_application_validates_before_loading_models_or_creating_logs(tmp_path, monkeypatch):
    from poirot.backend.app.bootstrap import bootstrap_runtime
    monkeypatch.setenv("POIROT_MULTIAGENT_ENABLED", "true")
    monkeypatch.setenv("POIROT_MULTIAGENT_L2_ENABLED", "true")
    with pytest.raises(ValueError, match="no configured mutation caller"):
        bootstrap_runtime(cli_overrides={"logs_root": str(tmp_path / "logs")})
    assert not (tmp_path / "logs").exists()
