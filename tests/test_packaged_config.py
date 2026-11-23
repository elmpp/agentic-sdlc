"""The tool's own config travels with the wheel, so a non-editable install can read it.

`uv tool install git+...` (or pipx) leaves no repository around the package, so
`_repo_root() / "config"` points above site-packages and every config read raises
FileNotFoundError. pyproject force-includes `config/` as `valxel_sdlc/_config`, and
`default_config_dir()` reads that copy when there is no repository.
"""

import tomllib
from pathlib import Path

from valxel_sdlc import config as cfg

REPO = Path(__file__).resolve().parents[1]
PACKAGED = "valxel_sdlc/_config"


def test_the_wheel_force_includes_the_config_directory():
    built = tomllib.loads((REPO / "pyproject.toml").read_text())["tool"]["hatch"]["build"]
    assert built["targets"]["wheel"]["force-include"] == {"config": PACKAGED}


def test_a_checkout_reads_the_repositorys_own_config(monkeypatch):
    monkeypatch.delenv("VALXEL_ROOT", raising=False)
    assert cfg.default_config_dir() == REPO / "config"
    assert (cfg.default_config_dir() / "template-contract.yaml").is_file()


def test_a_wheel_install_reads_the_packaged_copy(tmp_path, monkeypatch):
    """No repository above the package: the files shipped beside it are read instead."""
    pkg = tmp_path / "site-packages" / "valxel_sdlc"
    (pkg / "_config").mkdir(parents=True)
    (pkg / "_config" / "template-contract.yaml").write_text("capabilities: {}\n")
    monkeypatch.setattr(cfg, "__file__", str(pkg / "config.py"))
    monkeypatch.setenv("VALXEL_ROOT", str(tmp_path / "no-such-checkout"))

    assert cfg.default_config_dir() == pkg / "_config"
    got = cfg.config_file(tmp_path / "deployment", "template-contract.yaml")
    assert got == pkg / "_config" / "template-contract.yaml"


def test_a_deployments_own_file_still_wins(tmp_path, monkeypatch):
    monkeypatch.delenv("VALXEL_ROOT", raising=False)
    mine = tmp_path / "config"
    mine.mkdir()
    (mine / "models.yaml").write_text("roles: {}\n")
    assert cfg.config_file(mine, "models.yaml") == mine / "models.yaml"
    # One it doesn't override falls back to the tool's own.
    assert cfg.config_file(mine, "template-contract.yaml") == REPO / "config" / "template-contract.yaml"
