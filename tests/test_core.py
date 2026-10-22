"""Testes unitários para o módulo core."""

from python_template_linux.cli import main
from python_template_linux.core import format_environment_info, system_diagnostic


def test_system_diagnostic_returns_expected_keys():
    diag = system_diagnostic()
    expected_keys = {
        "python_version",
        "python_implementation",
        "system",
        "release",
        "architecture",
        "is_virtual_env",
    }
    assert expected_keys.issubset(diag.keys())
    assert isinstance(diag["python_version"], str)
    assert isinstance(diag["is_virtual_env"], bool)


def test_format_environment_info_contains_key_details():
    output = format_environment_info()
    diag = system_diagnostic()
    assert diag["python_version"] in output
    assert diag["system"] in output
    assert "Ambiente:" in output


def test_cli_main_executes_without_error(capsys):
    main()
    captured = capsys.readouterr()
    assert "Python" in captured.out
    assert "Ambiente:" in captured.out
