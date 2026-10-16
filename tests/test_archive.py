from pathlib import Path
from stat import S_IFLNK
from uuid import uuid4
from zipfile import ZipFile, ZipInfo

import pytest

from ta_mcp.archive import ArchiveError, inspect_archive
from ta_mcp.checks import run_available_checks
from ta_mcp.domain import GradingPolicy


def test_archive_inspection_rejects_traversal_links_and_duplicate_names(
    tmp_path: Path,
) -> None:
    """Catch ZIP Slip, symbolic links, duplicate paths, and corrupt inputs."""
    archive = tmp_path / "submission.zip"
    for name in ("../escape.py", "/absolute.py", "C:/drive.py", "dir\\escape.py"):
        with ZipFile(archive, "w") as zipped:
            zipped.writestr(name, "pass")
        with pytest.raises(ArchiveError):
            inspect_archive(archive)
    with ZipFile(archive, "w") as zipped:
        link = ZipInfo("link")
        link.create_system = 3
        link.external_attr = (S_IFLNK | 0o777) << 16
        zipped.writestr(link, "/etc/passwd")
    with pytest.raises(ArchiveError):
        inspect_archive(archive)
    archive.write_bytes(b"not a zip")
    with pytest.raises(ArchiveError):
        inspect_archive(archive)
    with ZipFile(archive, "w") as zipped:
        zipped.writestr("main.py", "print('ok')\n")
        zipped.writestr("pyproject.toml", "[project]\nname = 'sample'\n")
    before = archive.read_bytes()
    result = inspect_archive(archive)
    assert result.inspection.languages == ["Python"]
    assert result.inspection.build_systems == ["pyproject"]
    assert result.inspection.files[0].relative_path == "main.py"
    checks = run_available_checks(result, uuid4(), GradingPolicy())
    assert (
        next(check for check in checks if check.kind == "tests").status == "UNAVAILABLE"
    )
    assert next(check for check in checks if check.kind == "static").status == "PASSED"
    assert archive.read_bytes() == before
    assert not (tmp_path / "escape.py").exists()
