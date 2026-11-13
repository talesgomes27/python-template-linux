"""Testes unitários diretos dos módulos embutidos em scripts/init_project.sh."""

import os
import subprocess
import sys
import tomllib
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"

Loader = Callable[[str], ModuleType]


def test_generated_script_matches_sources(
    load_script: Callable[[Path], ModuleType],
) -> None:
    builder = load_script(SCRIPTS / "build_init_project.py")
    generated = (SCRIPTS / "init_project.sh").read_text(encoding="utf-8")
    assert generated == builder.render(), (
        "Execute: uv run python scripts/build_init_project.py"
    )
    assert generated.splitlines()[1].startswith("# ARQUIVO GERADO")
    assert "@@PYINIT_EMBED" not in generated


def test_builder_refuses_module_containing_heredoc_delimiter(
    load_script: Callable[[Path], ModuleType],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builder = load_script(SCRIPTS / "build_init_project.py")
    template = tmp_path / "init_project.sh.in"
    template.write_text(
        "#!/usr/bin/env bash\npython3 - <<'PY'\n@@PYINIT_EMBED:bad.py@@\nPY\n"
    )
    (tmp_path / "bad.py").write_text("print(1)\nPY\n")
    monkeypatch.setattr(builder, "TEMPLATE", template)
    monkeypatch.setattr(builder, "MODULES", tmp_path)
    with pytest.raises(ValueError, match="delimitador PY"):
        builder.render()


@pytest.mark.parametrize(
    ("value", "poetry", "expected"),
    [
        ("*", False, ""),
        ("", False, ""),
        ("1.2.3", False, "==1.2.3"),
        (">=1.0 , <2", False, ">=1.0,<2"),
        (">= 1.0, < 2", False, ">=1.0,<2"),
        ("^1.2.3", True, ">=1.2.3,<2.0.0"),
        ("^0.2.3", True, ">=0.2.3,<0.3.0"),
        ("^0.0.3", True, ">=0.0.3,<0.0.4"),
        ("^0", True, ">=0,<1"),
        ("~1.2.3", True, ">=1.2.3,<1.3.0"),
        ("~1", True, ">=1,<2"),
        ("~=1.4", True, "~=1.4"),
    ],
)
def test_version_constraint_translation(
    pyinit: Loader, value: str, poetry: bool, expected: str
) -> None:
    assert pyinit("migrate").version_constraint(value, poetry) == expected


@pytest.mark.parametrize(
    ("value", "poetry"),
    [
        ("^1.2 || ^2.0", True),
        ("^1.2.3.4", True),
        (">=1.0; python_version<'3.12'", False),
        ("git+https://example.invalid/pkg", False),
        ("1.0 @ file:///tmp/pkg", False),
    ],
)
def test_version_constraint_refuses_complex_input(
    pyinit: Loader, value: str, poetry: bool
) -> None:
    module = pyinit("migrate")
    with pytest.raises(module.Refused):
        module.version_constraint(value, poetry)


@pytest.mark.parametrize(
    ("spec", "requested", "expected"),
    [
        (">=3.11", "3.12", True),
        (">=3.11", "3.10", False),
        (">=3.11,<3.13", "3.13.1", False),
        ("==3.12.*", "3.12.7", True),
        ("!=3.12.*", "3.12", False),
        ("!=3.12", "3.12", True),
        (">3.12", "3.12", True),
        (">3.12", "3.12.0", False),
        ("~=3.11", "3.13.2", True),
        ("~=3.11.4", "3.12.0", False),
        ("<3.12.4", "3.12", True),
    ],
)
def test_python_allows(
    pyinit: Loader, spec: str, requested: str, expected: bool
) -> None:
    assert pyinit("migrate").python_allows(spec, requested) is expected


def test_python_allows_refuses_unsupported_clause(pyinit: Loader) -> None:
    module = pyinit("migrate")
    with pytest.raises(module.Refused):
        module.python_allows(">=3.11 ; os_name == 'posix'", "3.12")


def test_make_requirement_composes_extras_markers_and_optional(
    pyinit: Loader,
) -> None:
    module = pyinit("migrate")
    assert module.make_requirement("requests", "*") == ("requests", False)
    assert module.make_requirement(
        "uvicorn",
        {
            "version": "^0.30",
            "extras": ["standard"],
            "markers": "sys_platform == 'linux'",
            "optional": True,
        },
        True,
    ) == ("uvicorn[standard]>=0.30,<0.31; sys_platform == 'linux'", True)
    for name, value in (
        ("bad name", "*"),
        ("pkg", {"git": "https://example.invalid/pkg.git"}),
        ("pkg", ["1.0", "2.0"]),
    ):
        with pytest.raises(module.Refused):
            module.make_requirement(name, value)


def test_static_setup_reads_literals_without_executing(pyinit: Loader) -> None:
    module = pyinit("migrate")
    values = module.static_setup(
        b'"""Pacote."""\n'
        b"from setuptools import setup\n"
        b'setup(name="sample", install_requires=["requests>=2"])\n'
    )
    assert values == {"name": "sample", "install_requires": ["requests>=2"]}
    for source in (
        b"import os\nfrom setuptools import setup\nsetup(name='x')\n",
        b"from setuptools import setup\nsetup(name=open('n').read())\n",
        b"from setuptools import setup\nsetup(name='x', cmdclass={})\n",
        b"from setuptools import setup\nif True:\n    setup(name='x')\n",
        b"from setuptools import setup\nsetup(name='x')\nsetup(name='y')\n",
    ):
        with pytest.raises(module.Refused):
            module.static_setup(source)


def test_configure_tools_adds_only_missing_families(
    pyinit: Loader, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = pyinit("configure_tools")
    manifest = tmp_path / "pyproject.toml"
    original = b'[project]\nname = "sample"\n\n[tool.ruff]\nline-length = 101\n'
    manifest.write_bytes(original)
    assert module.main(["configure_tools.py", str(manifest), "check"]) == 0
    assert manifest.read_bytes() == original
    assert module.main(["configure_tools.py", str(manifest), "apply"]) == 0
    final = manifest.read_bytes()
    assert (
        final
        == original
        + "".join(module.DEFAULTS[name] for name in ("pytest", "mypy")).encode()
    )
    data = tomllib.loads(final.decode())
    assert data["tool"]["ruff"] == {"line-length": 101}
    assert data["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"]
    assert capsys.readouterr().out == (
        "  ruff: preservado.\n"
        "  pytest: configuracao padrao criada.\n"
        "  mypy: configuracao padrao criada.\n"
    )


def test_configure_tools_refuses_invalid_or_inline_configuration(
    pyinit: Loader, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = pyinit("configure_tools")
    manifest = tmp_path / "pyproject.toml"
    for content in (
        b"tool = { ruff = { line-length = 100 } }\n",
        b'[tool]\nruff = "invalid"\n',
        b"[project\n",
    ):
        manifest.write_bytes(content)
        assert module.main(["configure_tools.py", str(manifest), "apply"]) == 2
        assert manifest.read_bytes() == content
        assert "composicao Ruff/pytest recusada" in capsys.readouterr().err
    assert module.main(["configure_tools.py", str(tmp_path / "absent"), "check"]) == 0


def test_envrc_snapshot_token_tracks_content_and_metadata(
    pyinit: Loader, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = pyinit("envrc_snapshot")
    monkeypatch.chdir(tmp_path)
    envrc = tmp_path / ".envrc"
    envrc.write_bytes(b"use devshell_python\n")
    envrc.chmod(0o600)
    token, data = module.snapshot()
    assert data == b"use devshell_python\n"
    assert module.snapshot()[0] == token
    assert module.main(["envrc_snapshot.py", "verify", token]) == 0
    envrc.chmod(0o700)
    assert module.snapshot()[0] != token
    envrc.chmod(0o600)
    envrc.write_bytes(b"use devshell_python\nexport A=1\n")
    assert module.main(["envrc_snapshot.py", "verify", token]) == 2


def test_envrc_snapshot_refuses_unsafe_files(
    pyinit: Loader, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = pyinit("envrc_snapshot")
    monkeypatch.chdir(tmp_path)
    envrc = tmp_path / ".envrc"
    with pytest.raises(FileNotFoundError):
        module.snapshot()
    envrc.write_text("use devshell_python\n")
    envrc.chmod(0o664)
    with pytest.raises(ValueError, match="arquivo regular proprio"):
        module.snapshot()
    envrc.chmod(0o600)
    os.link(envrc, tmp_path / "alias")
    with pytest.raises(ValueError, match="hardlinks"):
        module.snapshot()
    envrc.unlink()
    envrc.symlink_to(tmp_path / "alias")
    with pytest.raises(OSError):
        module.snapshot()


def test_envrc_snapshot_escapes_control_characters(pyinit: Loader) -> None:
    escaped = pyinit("envrc_snapshot").escaped(b"a\tb\n\x1b[31m\xff\r")
    assert escaped == "a\tb\n\\x1b[31m\\xff\\r"


def test_modules_run_isolated_from_stdin_like_the_generator(tmp_path: Path) -> None:
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text('[project]\nname = "sample"\n')
    source = (SCRIPTS / "pyinit/configure_tools.py").read_bytes()
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-", str(manifest), "apply"],
        input=source,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    tools = tomllib.loads(manifest.read_text())["tool"]
    assert set(tools) == {"ruff", "pytest", "mypy"}
    assert tools["mypy"]["files"] == ["src", "tests"]


def test_builder_requires_pinned_action_in_template_workflow(
    load_script: Callable[[Path], ModuleType],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builder = load_script(SCRIPTS / "build_init_project.py")
    assert set(builder.pinned_actions()) == {"actions/checkout", "astral-sh/setup-uv"}
    template = tmp_path / "init_project.sh.in"
    template.write_text("#!/usr/bin/env bash\n# uses: @@ACTION:example/missing@@\n")
    monkeypatch.setattr(builder, "TEMPLATE", template)
    with pytest.raises(ValueError, match="example/missing"):
        builder.render()


def test_configure_tools_never_blocks_on_optional_mypy_family(
    pyinit: Loader, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    content = b'tool = {ruff = {line-length = 101}, pytest = {addopts = ["-x"]}}\n'
    module = pyinit("configure_tools")
    manifest = tmp_path / "pyproject.toml"
    manifest.write_bytes(content)
    assert module.main(["configure_tools.py", str(manifest), "apply"]) == 0
    assert manifest.read_bytes() == content
    assert "  mypy: nao adicionado; componha manualmente.\n" in capsys.readouterr().out


def test_configure_tools_preserves_existing_mypy_family(
    pyinit: Loader, tmp_path: Path
) -> None:
    module = pyinit("configure_tools")
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text("[tool.mypy]\nstrict = true\n")
    assert module.main(["configure_tools.py", str(manifest), "apply"]) == 0
    assert tomllib.loads(manifest.read_text())["tool"]["mypy"] == {"strict": True}
