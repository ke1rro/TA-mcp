import hashlib
import io
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from uuid import NAMESPACE_URL, uuid5
from zipfile import BadZipFile, ZipFile

from ta_mcp.domain import (
    ArchiveInspection,
    FileContent,
    SubmissionArchive,
    SubmissionFile,
    canonical_path,
)

MAX_ARCHIVE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024
MAX_FILE_BYTES = 1024 * 1024
MAX_FILES = 1000
MAX_PREVIEW_CHARS = 65536
MAX_TOTAL_PREVIEW_CHARS = 160000
LANGUAGES = {
    ".py": "Python",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".hpp": "C++",
    ".java": "Java",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".rs": "Rust",
    ".go": "Go",
    ".cs": "C#",
    ".rb": "Ruby",
    ".jl": "Julia",
}
BUILD_SYSTEMS = {
    "pyproject.toml": "pyproject",
    "requirements.txt": "pip",
    "Makefile": "make",
    "CMakeLists.txt": "cmake",
    "package.json": "npm",
    "Cargo.toml": "cargo",
    "go.mod": "go",
    "pom.xml": "maven",
    "build.gradle": "gradle",
}


class ArchiveError(ValueError):
    """Invalid, oversized, or unsafe ZIP archive."""


@dataclass(frozen=True)
class InspectedArchive:
    """Ephemeral manifest plus bounded, fully decoded source text."""

    inspection: ArchiveInspection
    texts: dict[str, str]


def read_bounded_archive(path: Path) -> bytes:
    """Read at most the configured compressed archive byte limit."""
    with path.open("rb") as stream:
        content = stream.read(MAX_ARCHIVE_BYTES + 1)
    if len(content) > MAX_ARCHIVE_BYTES:
        raise ArchiveError("ZIP exceeds the 10 MiB compressed-size limit")
    return content


def inspect_archive(
    path: Path, requested_paths: list[str] | None = None
) -> InspectedArchive:
    """Inspect a bounded ZIP in memory without extracting or executing files.

    Validate the entire central directory before reading members. Reject aliases,
    traversal, links, special files, encryption, excessive expansion, and CRC errors.
    Binary files stay in the manifest but are never represented as source text.

    Args:
        path: User-authorized local archive path.
        requested_paths: Canonical text paths to preview within a shared budget.

    Returns:
        Validated metadata and ephemeral source contents for evidence verification.
    """
    try:
        content = read_bounded_archive(path)
        digest = hashlib.sha256(content).hexdigest()
        submission = SubmissionArchive(
            id=uuid5(NAMESPACE_URL, f"ta-mcp:{path.name}:{digest}"),
            archive_name=path.name,
            sha256=digest,
            byte_size=len(content),
            created_at=datetime.fromtimestamp(path.stat().st_mtime, UTC),
        )
        with ZipFile(io.BytesIO(content)) as zipped:
            members = zipped.infolist()
            if len(members) > MAX_FILES:
                raise ArchiveError("ZIP exceeds the 1000-entry limit")
            names: set[str] = set()
            total_bytes = 0
            for member in members:
                name = member.filename[:-1] if member.is_dir() else member.filename
                canonical_path(name)
                if name in names or member.orig_filename != member.filename:
                    raise ArchiveError("ZIP contains duplicate or NUL-aliased paths")
                names.add(name)
                mode = member.external_attr >> 16
                file_type = stat.S_IFMT(mode)
                if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
                    raise ArchiveError("ZIP contains a link or special file")
                if member.flag_bits & 1:
                    raise ArchiveError("Encrypted ZIP entries are unsupported")
                if member.file_size > MAX_FILE_BYTES:
                    raise ArchiveError("ZIP member exceeds the 1 MiB limit")
                total_bytes += member.file_size
                if total_bytes > MAX_TOTAL_BYTES:
                    raise ArchiveError("ZIP exceeds the 20 MiB expanded-size limit")
                if member.file_size > max(member.compress_size, 1) * 100:
                    raise ArchiveError("ZIP entry exceeds the 100:1 expansion ratio")
            files = []
            texts: dict[str, str] = {}
            for member in sorted(members, key=lambda item: item.filename):
                if member.is_dir():
                    continue
                with zipped.open(member) as stream:
                    data = stream.read(MAX_FILE_BYTES + 1)
                if len(data) != member.file_size or len(data) > MAX_FILE_BYTES:
                    raise ArchiveError("ZIP member size disagrees with its manifest")
                text: str | None = None
                if b"\x00" not in data:
                    try:
                        text = data.decode("utf-8")
                    except UnicodeDecodeError:
                        text = None
                if text is not None:
                    texts[member.filename] = text
                files.append(
                    SubmissionFile(
                        id=uuid5(submission.id, member.filename),
                        submission_id=submission.id,
                        relative_path=member.filename,
                        sha256=hashlib.sha256(data).hexdigest(),
                        byte_size=len(data),
                        language=LANGUAGES.get(
                            PurePosixPath(member.filename).suffix.lower()
                        ),
                        line_count=None if text is None else len(text.splitlines()),
                    )
                )
            selected = (
                set(requested_paths) if requested_paths is not None else set(texts)
            )
            for name in selected:
                canonical_path(name)
                if name not in texts:
                    raise ArchiveError(
                        f"Requested UTF-8 text file is unavailable: {name}"
                    )
            remaining = MAX_TOTAL_PREVIEW_CHARS
            previews = []
            for entry in files:
                if entry.relative_path not in selected or remaining <= 0:
                    continue
                text = texts[entry.relative_path]
                preview = text[: min(MAX_PREVIEW_CHARS, remaining)]
                previews.append(
                    FileContent(
                        submission_file_id=entry.id,
                        text=preview,
                        is_truncated=len(preview) < len(text),
                    )
                )
                remaining -= len(preview)
            return InspectedArchive(
                ArchiveInspection(
                    submission=submission,
                    files=files,
                    contents=previews,
                    languages=sorted(
                        {entry.language for entry in files if entry.language}
                    ),
                    build_systems=sorted(
                        {
                            BUILD_SYSTEMS[PurePosixPath(entry.relative_path).name]
                            for entry in files
                            if PurePosixPath(entry.relative_path).name in BUILD_SYSTEMS
                        }
                    ),
                ),
                texts,
            )
    except (
        OSError,
        BadZipFile,
        RuntimeError,
        NotImplementedError,
        ValueError,
    ) as error:
        raise ArchiveError(str(error)) from error
