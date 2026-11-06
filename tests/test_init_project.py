"""Executa o gerador sem downloads, autorização direnv ou commits reais."""

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/init_project.sh"


@pytest.fixture
def scaffold(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    home = tmp_path / "home"
    tools = tmp_path / "tools"
    git_template = tmp_path / "git-template"
    workspace = tmp_path / "workspace com espaços"
    for directory in (home, tools, git_template, workspace):
        directory.mkdir(mode=0o700)
    uv = shutil.which("uv")
    git = shutil.which("git")
    assert uv and git, "Os testes do gerador exigem uv e Git instalados"
    env = {
        "HOME": str(home),
        "PATH": str(tools) + os.pathsep + os.defpath,
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local/share"),
        "XDG_STATE_HOME": str(home / ".local/state"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "UV_CACHE_DIR": str(home / ".cache/uv"),
        "UV_PYTHON_INSTALL_DIR": str(home / ".local/share/uv/python"),
        "UV_BIN": str(tools / "uv"),
        "TEST_REAL_UV": uv,
        "TEST_REAL_GIT": git,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TEMPLATE_DIR": str(git_template),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    # Simular somente instalação/resolução; a .venv é criada pelo uv real offline.
    (tools / "uv").write_text(
        f"#!{sys.executable}\n"
        "import os, subprocess, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['python', 'install']:\n"
        "    pass\n"
        "elif args[:1] == ['init']:\n"
        "    Path('pyproject.toml').write_text(\n"
        '        \'[project]\\nname = "sample"\\nversion = "0.1.0"\\n\')\n'
        "    Path('.gitignore').write_text('.venv/\\n')\n"
        "elif args[:2] == ['python', 'pin']:\n"
        "    Path('.python-version').write_text(args[2] + '\\n')\n"
        "elif args[:1] == ['add']:\n"
        "    pass\n"
        "elif args == ['sync']:\n"
        "    if os.environ.get('TEST_SYNC_FAILURE'):\n"
        "        sys.exit(27)\n"
        "    if not Path('.venv/pyvenv.cfg').exists():\n"
        "        subprocess.run([os.environ['TEST_REAL_UV'],\n"
        "            '--no-config', '--no-cache', '--offline', 'venv',\n"
        "            '--no-project', '--no-python-downloads',\n"
        "            '--python', sys.executable, '.venv'], check=True)\n"
        "else:\n"
        "    raise SystemExit('uv inesperado: ' + repr(args))\n"
    )
    # Registrar tentativas proibidas sem criar commits nem stage, mesmo no teste RED.
    (tools / "git").write_text(
        f"#!{sys.executable}\n"
        "import os, subprocess, sys\n"
        "from pathlib import Path\n"
        "if sys.argv[1] in ('add', 'commit', 'push'):\n"
        "    with (Path(os.environ['HOME']) / 'forbidden-git').open('a') as log:\n"
        "        log.write(sys.argv[1] + '\\n')\n"
        "else:\n"
        "    sys.exit(subprocess.call([os.environ['TEST_REAL_GIT'], *sys.argv[1:]]))\n"
    )
    (tools / "direnv").write_text(
        "#!/bin/sh\n"
        'mkdir -p "$XDG_DATA_HOME/direnv/allow"\n'
        'touch "$XDG_DATA_HOME/direnv/allow/unreviewed"\n'
    )
    for tool in ("uv", "git", "direnv"):
        (tools / tool).chmod(0o700)
    return workspace, env


def run_init(
    scaffold: tuple[Path, dict[str, str]], target: Path, *args: str
) -> subprocess.CompletedProcess[str]:
    workspace, env = scaffold
    return subprocess.run(
        ["bash", str(SCRIPT), str(target), *args],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
        preexec_fn=lambda: os.umask(0o002),
        timeout=30,
    )


def test_creates_envrc_without_authorizing_it(
    scaffold: tuple[Path, dict[str, str]],
) -> None:
    workspace, env = scaffold
    target = workspace / "new-project"
    result = run_init(scaffold, target)
    assert result.returncode == 0, result.stderr
    assert (target / ".envrc").read_text() == "use devshell_python\n"
    assert stat.S_IMODE((target / ".envrc").stat().st_mode) == 0o600
    assert not (Path(env["XDG_DATA_HOME"]) / "direnv/allow").exists()
    assert "direnv allow ." in result.stdout


def test_new_directories_are_safe_under_permissive_umask(
    scaffold: tuple[Path, dict[str, str]],
) -> None:
    workspace, _ = scaffold
    target = workspace / "nested/new-project"
    result = run_init(scaffold, target)
    assert result.returncode == 0, result.stderr
    for directory in (target.parent, target, target / ".vscode", target / ".venv/bin"):
        assert not directory.stat().st_mode & 0o022, directory
    assert (target / ".venv/pyvenv.cfg").is_file()
    assert os.access(target / ".venv/bin/python", os.X_OK)


def test_git_is_initialized_without_staging_or_committing(
    scaffold: tuple[Path, dict[str, str]],
) -> None:
    workspace, env = scaffold
    target = workspace / "new-project"
    result = run_init(scaffold, target)
    assert result.returncode == 0, result.stderr
    assert (target / ".git").is_dir()
    assert not (Path(env["HOME"]) / "forbidden-git").exists()
    head = subprocess.run(
        [env["TEST_REAL_GIT"], "rev-parse", "--verify", "HEAD"],
        cwd=target,
        env=env,
        capture_output=True,
        text=True,
    )
    assert head.returncode != 0
    staged = subprocess.run(
        [env["TEST_REAL_GIT"], "diff", "--cached", "--name-only"],
        cwd=target,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert staged.stdout == ""


def test_existing_envrc_and_permissions_are_preserved(
    scaffold: tuple[Path, dict[str, str]],
) -> None:
    workspace, _ = scaffold
    target = workspace / "existing-project"
    target.mkdir()
    target.chmod(0o775)
    envrc = target / ".envrc"
    envrc.write_text("export PROJECT_VALUE=original\n")
    envrc.chmod(0o640)
    result = run_init(scaffold, target)
    assert result.returncode == 0, result.stderr
    assert envrc.read_text() == "export PROJECT_VALUE=original\n"
    assert stat.S_IMODE(envrc.stat().st_mode) == 0o640
    assert stat.S_IMODE(target.stat().st_mode) == 0o775


def test_dangling_envrc_symlink_is_not_followed(
    scaffold: tuple[Path, dict[str, str]],
) -> None:
    workspace, _ = scaffold
    target = workspace / "existing-project"
    target.mkdir()
    destination = workspace / "do-not-create"
    (target / ".envrc").symlink_to(destination)
    result = run_init(scaffold, target)
    assert result.returncode == 0, result.stderr
    assert (target / ".envrc").is_symlink()
    assert not destination.exists()


def test_existing_git_file_is_preserved(scaffold: tuple[Path, dict[str, str]]) -> None:
    workspace, _ = scaffold
    target = workspace / "existing-project"
    target.mkdir()
    git_file = target / ".git"
    git_file.write_text("gitdir: /worktree-metadata\n")
    result = run_init(scaffold, target)
    assert result.returncode == 0, result.stderr
    assert git_file.read_text() == "gitdir: /worktree-metadata\n"


def test_uv_failure_stops_before_creating_envrc(
    scaffold: tuple[Path, dict[str, str]],
) -> None:
    workspace, env = scaffold
    env["TEST_SYNC_FAILURE"] = "1"
    target = workspace / "new-project"
    result = run_init(scaffold, target)
    assert result.returncode == 27
    assert not (target / ".envrc").exists()
    assert not (Path(env["XDG_DATA_HOME"]) / "direnv/allow").exists()
