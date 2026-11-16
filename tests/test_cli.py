from typer.testing import CliRunner

from recommerce.cli import app
from recommerce.ingest import PipelineResult

runner = CliRunner()


def test_help_lists_operational_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "init-db" in result.stdout
    assert "generate" in result.stdout
    assert "ingest" in result.stdout
    assert "quality" in result.stdout
    assert "export-metrics" in result.stdout


def test_generate_creates_partition_without_database(tmp_path) -> None:
    result = runner.invoke(
        app,
        [
            "generate",
            "--start-date",
            "2026-11-15",
            "--days",
            "1",
            "--users",
            "20",
            "--listings-per-day",
            "10",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "2026-11-15" / "orders.csv").exists()
    assert '"days": 1' in result.stdout


def test_expect_replay_fails_if_a_file_was_new(monkeypatch, tmp_path):
    import uuid

    monkeypatch.setattr("recommerce.cli.database_url", lambda: "configured")
    monkeypatch.setattr(
        "recommerce.cli.ingest_directory",
        lambda *_: PipelineResult(uuid.uuid4(), 4, 1, 3, 1, 0),
    )
    result = runner.invoke(app, ["ingest", "--input-dir", str(tmp_path), "--expect-replay"])
    assert result.exit_code == 1


def test_expect_replay_passes_only_when_all_files_skipped(monkeypatch, tmp_path):
    import uuid

    monkeypatch.setattr("recommerce.cli.database_url", lambda: "configured")
    monkeypatch.setattr(
        "recommerce.cli.ingest_directory",
        lambda *_: PipelineResult(uuid.uuid4(), 4, 0, 4, 0, 0),
    )
    result = runner.invoke(app, ["ingest", "--input-dir", str(tmp_path), "--expect-replay"])
    assert result.exit_code == 0
