"""Installs made under the previous project name keep working, without deleting anything."""
import os

from aether import legacy_compat

OLD = "jar" + "vis"


def test_env_and_dotenv_keys_map_to_new_names(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(OLD.upper() + "_SAMPLE_ONE", "one")
    (tmp_path / ".env").write_text(OLD.upper() + "_SAMPLE_TWO='two'\nAETHER_SAMPLE_THREE=keep\n")
    monkeypatch.setenv("AETHER_SAMPLE_THREE", "already-set")
    monkeypatch.delenv("AETHER_SAMPLE_ONE", raising=False)
    monkeypatch.delenv("AETHER_SAMPLE_TWO", raising=False)
    legacy_compat._map_environment()
    assert os.environ["AETHER_SAMPLE_ONE"] == "one"
    assert os.environ["AETHER_SAMPLE_TWO"] == "two"
    assert os.environ["AETHER_SAMPLE_THREE"] == "already-set"
    for name in ("AETHER_SAMPLE_ONE", "AETHER_SAMPLE_TWO"):
        monkeypatch.delenv(name, raising=False)


def test_legacy_data_is_copied_not_moved_and_never_overwrites(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / (OLD + ".sqlite3")).write_text("old")
    (tmp_path / "data" / "aether-existing.txt").write_text("new")
    (tmp_path / "data" / (OLD + "-existing.txt")).write_text("old")
    legacy_home = tmp_path / "home" / ("." + OLD)
    legacy_home.mkdir(parents=True)
    (legacy_home / "state.json").write_text("{}")
    legacy_compat._copy_legacy_data()
    assert (tmp_path / "data" / "aether.sqlite3").read_text() == "old"
    assert (tmp_path / "data" / (OLD + ".sqlite3")).exists()
    assert (tmp_path / "data" / "aether-existing.txt").read_text() == "new"
    assert (tmp_path / "home" / ".aether" / "state.json").exists()
    assert (legacy_home / "state.json").exists()
