"""Behaviour without optional extras, run in a real virtualenv that has none of them.

A fresh environment with only the base dependencies replaces patching modules out:
PyYAML, rich, typer and WeasyPrint are genuinely absent there.
"""

import json
import shutil
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

STORAGE_PRELUDE = """
import json, sys
from pydantic import BaseModel
from py_invoices.backends.files.storage import FileStorage

class Entity(BaseModel):
    id: int
    name: str
    data: dict | None = None

storage = FileStorage(sys.argv[1], "test_entity", Entity)
"""


@pytest.fixture(scope="session")
def bare_python(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Interpreter of a virtualenv with py-invoices and only its base dependencies."""
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is needed to build the no-extras environment")
    venv = tmp_path_factory.mktemp("no-extras") / "venv"
    subprocess.run([uv, "venv", "-q", "--python", sys.executable, str(venv)], check=True)  # nosec B603
    python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    subprocess.run(  # nosec B603
        [uv, "pip", "install", "-q", "--python", str(python), str(PROJECT_ROOT)], check=True
    )
    return python


def run(python: Path, code: str, *args: str) -> Any:
    """Run `code` with `python`; it must print one JSON value."""
    result = subprocess.run(  # nosec B603
        [str(python), "-c", code, *args], capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)


def test_environment_has_no_extras(bare_python: Path) -> None:
    code = (
        "import importlib.util, json; "
        "print(json.dumps({m: importlib.util.find_spec(m) is not None "
        "for m in ['yaml', 'rich', 'typer', 'weasyprint']}))"
    )

    assert run(bare_python, code) == {
        "yaml": False,
        "rich": False,
        "typer": False,
        "weasyprint": False,
    }


def test_clean_import_no_extras(bare_python: Path) -> None:
    """The package and the files backend import without any optional dependency."""
    code = (
        "import json, py_invoices; from py_invoices.backends.files import storage; "
        "print(json.dumps(py_invoices.__version__))"
    )

    assert run(bare_python, code)


def test_json_and_markdown_work_without_pyyaml(bare_python: Path, tmp_path: Path) -> None:
    code = (
        STORAGE_PRELUDE
        + """
storage.save(Entity(id=1, name="as_json", data={"a": 1}), 1, fmt="json")
md_path = storage.save(Entity(id=2, name="as_md", data={"foo": "bar"}), 2, fmt="md")
print(json.dumps({
    "json": storage.load(1).name,
    "md": storage.load(2).name,
    "md_content": open(md_path).read(),
}))
"""
    )

    result = run(bare_python, code, str(tmp_path))

    assert result["json"] == "as_json"
    assert result["md"] == "as_md"
    assert '{\n  "id": 2' in result["md_content"]


def test_saving_yaml_requires_pyyaml(bare_python: Path, tmp_path: Path) -> None:
    code = (
        STORAGE_PRELUDE
        + """
try:
    storage.save(Entity(id=3, name="no_yaml", data={}), 3, fmt="yaml")
except ImportError as e:
    print(json.dumps(str(e)))
"""
    )

    message = run(bare_python, code, str(tmp_path))
    assert "3.yaml is stored as YAML, but PyYAML is not installed" in message
    assert "pip install 'py-invoices[yaml]'" in message


def test_loading_yaml_requires_pyyaml(bare_python: Path, tmp_path: Path) -> None:
    entity_dir = tmp_path / "test_entity"
    entity_dir.mkdir()
    (entity_dir / "3.yaml").write_text("id: 3\nname: manual_yaml\n")
    code = (
        STORAGE_PRELUDE
        + """
try:
    storage.load(3)
except ImportError as e:
    print(json.dumps(str(e)))
"""
    )

    message = run(bare_python, code, str(tmp_path))
    assert "3.yaml is stored as YAML, but PyYAML is not installed" in message
    assert "pip install 'py-invoices[yaml]'" in message


YAML_COMPANY = "---\nid: 1\nname: Acme\naddress: Street 1\n---\n"


def test_loading_yaml_frontmatter_requires_pyyaml(bare_python: Path, tmp_path: Path) -> None:
    """Markdown with YAML frontmatter names the file and the extra, not a JSONDecodeError."""
    entity_dir = tmp_path / "test_entity"
    entity_dir.mkdir()
    (entity_dir / "4.acme.md").write_text("---\nid: 4\nname: acme\n---\n")
    code = (
        STORAGE_PRELUDE
        + """
from py_invoices.backends.files.storage import YamlUnavailableError
try:
    storage.load(4)
except YamlUnavailableError as e:
    print(json.dumps({"message": str(e), "file": str(e.file)}))
"""
    )

    result = run(bare_python, code, str(tmp_path))

    assert result["file"] == str(entity_dir / "4.acme.md")
    assert "4.acme.md is stored as YAML" in result["message"]
    assert "pip install 'py-invoices[yaml]'" in result["message"]


def test_files_backend_fails_fast_on_yaml_frontmatter(bare_python: Path, tmp_path: Path) -> None:
    """Opening a store that holds YAML fails at once, before any command reads it."""
    (tmp_path / "companies").mkdir()
    (tmp_path / "companies" / "1.acme.md").write_text(YAML_COMPANY)
    code = """
import json, sys
from py_invoices import RepositoryFactory
from py_invoices.backends.files.storage import YamlUnavailableError
try:
    RepositoryFactory(backend="files", root_dir=sys.argv[1], file_format="md")
except YamlUnavailableError as e:
    print(json.dumps(str(e.file)))
"""

    assert run(bare_python, code, str(tmp_path)) == str(tmp_path / "companies" / "1.acme.md")


@pytest.fixture(scope="session")
def cli_python(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Interpreter of a virtualenv with py-invoices[cli] and no PyYAML."""
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is needed to build the no-yaml environment")
    venv = tmp_path_factory.mktemp("cli-no-yaml") / "venv"
    subprocess.run([uv, "venv", "-q", "--python", sys.executable, str(venv)], check=True)  # nosec B603
    python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    subprocess.run(  # nosec B603
        [uv, "pip", "install", "-q", "--python", str(python), f"{PROJECT_ROOT}[cli]"], check=True
    )
    return python


@pytest.fixture
def yaml_store(tmp_path: Path) -> Path:
    """A files store written with YAML frontmatter, as `setup` with the md format makes it."""
    (tmp_path / "companies").mkdir()
    (tmp_path / "companies" / "1.acme.md").write_text(YAML_COMPANY)
    (tmp_path / ".env").write_text(
        "INVOICES_BACKEND=files\nINVOICES_STORAGE_PATH=.\nINVOICES_FILE_FORMAT=md\n"
    )
    return tmp_path


def run_cli(python: Path, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603
        [str(python), "-m", "py_invoices.cli.main", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env={"PATH": "", "COLUMNS": "200"},
    )


def test_cli_without_pyyaml_exits_with_missing_dependency(
    cli_python: Path, yaml_store: Path
) -> None:
    result = run_cli(cli_python, yaml_store, "invoices", "list")

    error = json.loads(result.stdout)["error"]
    assert result.returncode == 4, result.stderr
    assert error["code"] == "MISSING_DEPENDENCY"
    assert error["context"] == {"extra": "yaml"}
    assert "companies/1.acme.md is stored as YAML" in error["message"]
    assert "Traceback" not in result.stderr


def test_typer_cli_without_pyyaml_names_the_extra(cli_python: Path, yaml_store: Path) -> None:
    result = run_cli(cli_python, yaml_store, "companies", "list")

    assert result.returncode == 1
    assert "pip install 'py-invoices[yaml]'" in result.stdout
    assert "1.acme.md is stored as YAML" in result.stdout
    assert "Traceback" not in result.stdout + result.stderr
