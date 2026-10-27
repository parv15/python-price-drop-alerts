from price_alerts import cli


def test_config_error_exits_1(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "watchlist.yaml").write_text("settings: {}\nitems: []\n")
    assert cli.main(["--dry-run"]) == 1


def test_missing_token_exits_1(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no .env here
    monkeypatch.delenv("MAILTRAP_API_TOKEN", raising=False)
    monkeypatch.delenv("DRY_RUN", raising=False)
    (tmp_path / "watchlist.yaml").write_text(
        "settings:\n  from_email: a@example.com\n  default_recipients: [b@example.com]\n"
        "items:\n  - name: X\n    url: https://example.com/x\n"
    )
    assert cli.main([]) == 1


def test_ui_subcommand_parses_its_own_options():
    from price_alerts.cli import build_ui_parser

    args = build_ui_parser().parse_args(["--port", "9000", "--open"])
    assert args.port == 9000 and args.open_browser is True and args.host == "127.0.0.1"
    assert str(args.watchlist) == "watchlist.yaml" and str(args.data_dir) == "data"


def test_main_hands_ui_to_the_dashboard(monkeypatch):
    from price_alerts import cli

    seen = {}
    monkeypatch.setattr(cli, "ui_main", lambda argv: seen.setdefault("argv", argv) and 0)
    assert cli.main(["ui", "--port", "1234"]) == 0
    assert seen["argv"] == ["--port", "1234"]
