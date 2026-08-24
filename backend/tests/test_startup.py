from pathlib import Path
import subprocess
import sys


def test_main_app_imports_from_backend_working_directory() -> None:
    backend_directory = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from main import app; "
                "print(any(route.path == '/api/run' for route in app.routes))"
            ),
        ],
        cwd=backend_directory,
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True"


def test_main_app_imports_from_project_root() -> None:
    project_root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from main import app; "
                "print(any(route.path == '/api/run' for route in app.routes))"
            ),
        ],
        cwd=project_root,
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True"
