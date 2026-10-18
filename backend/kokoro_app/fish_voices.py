from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from uuid import uuid4

from kokoro_app.schemas import FishVoiceInput, FishVoicePage, FishVoiceReference


class VoiceLibraryError(RuntimeError):
    def __init__(self, message: str, code: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class FishVoiceLibrary:
    """A shared local library, independent of expiring generated audio."""

    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.path)) as connection, connection:
                connection.row_factory = sqlite3.Row
                # Serialize initialization and mutations across threads/processes.
                connection.execute("BEGIN IMMEDIATE")
                exists = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'fish_voices'"
                ).fetchone()
                if not exists:
                    connection.execute(
                        "CREATE TABLE fish_voices (id TEXT PRIMARY KEY, name TEXT NOT NULL, "
                        "reference_id TEXT NOT NULL UNIQUE, description TEXT NOT NULL DEFAULT '')"
                    )
                    connection.execute(
                        "INSERT INTO fish_voices (id, name, reference_id) VALUES (?, ?, ?)",
                        (uuid4().hex, "Original Fish voice", "b0204e37cbc94a16954c78697b844af2"),
                    )
                columns = {row["name"] for row in connection.execute("PRAGMA table_info(fish_voices)")}
                if "description" not in columns:
                    connection.execute("ALTER TABLE fish_voices ADD COLUMN description TEXT NOT NULL DEFAULT ''")
                yield connection
        except sqlite3.IntegrityError as error:
            raise VoiceLibraryError(
                "This Fish reference ID is already saved. Select or edit the existing voice.",
                "duplicate_voice_reference", 409,
            ) from error
        except (sqlite3.Error, OSError) as error:
            raise VoiceLibraryError(
                "The voice library could not be read or saved. Check the runtime folder permissions and free disk space, then retry.",
                "voice_library_unavailable", 503,
            ) from error

    @staticmethod
    def _get(connection: sqlite3.Connection, identifier: str) -> FishVoiceReference:
        row = connection.execute("SELECT * FROM fish_voices WHERE id = ?", (identifier,)).fetchone()
        if row is None:
            raise VoiceLibraryError(
                "This saved voice no longer exists. Reload the voice list.",
                "voice_reference_not_found", 404,
            )
        return FishVoiceReference(**dict(row))

    def list(self) -> list[FishVoiceReference]:
        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM fish_voices ORDER BY name COLLATE NOCASE, id").fetchall()
            return [FishVoiceReference(**dict(row)) for row in rows]

    def create(self, voice: FishVoiceInput) -> FishVoiceReference:
        saved = FishVoiceReference(id=uuid4().hex, **voice.model_dump())
        with self._connection() as connection:
            self._ensure_unique_reference(connection, voice.reference_id)
            connection.execute(
                "INSERT INTO fish_voices (id, name, reference_id, description) VALUES (?, ?, ?, ?)",
                (saved.id, saved.name, saved.reference_id, saved.description),
            )
        return saved

    def update(self, identifier: str, voice: FishVoiceInput) -> FishVoiceReference:
        with self._connection() as connection:
            self._get(connection, identifier)
            self._ensure_unique_reference(connection, voice.reference_id, identifier)
            connection.execute(
                "UPDATE fish_voices SET name = ?, reference_id = ?, description = ? WHERE id = ?",
                (voice.name, voice.reference_id, voice.description, identifier),
            )
        return FishVoiceReference(id=identifier, **voice.model_dump())

    @staticmethod
    def _ensure_unique_reference(connection: sqlite3.Connection, reference: str, identifier: str = "") -> None:
        # Old libraries may contain uppercase IDs. Compare without changing stored
        # values so even previously accepted references remain readable/deletable.
        existing = connection.execute(
            "SELECT 1 FROM fish_voices WHERE reference_id = ? COLLATE NOCASE AND id != ?",
            (reference, identifier),
        ).fetchone()
        if existing:
            raise VoiceLibraryError(
                "This Fish reference ID is already saved. Select or edit the existing voice.",
                "duplicate_voice_reference", 409,
            )

    def page(self, page: int, page_size: int) -> FishVoicePage:
        with self._connection() as connection:
            total = connection.execute("SELECT COUNT(*) FROM fish_voices").fetchone()[0]
            rows = connection.execute(
                "SELECT * FROM fish_voices ORDER BY name COLLATE NOCASE, id LIMIT ? OFFSET ?",
                (page_size, (page - 1) * page_size),
            ).fetchall()
            return FishVoicePage(items=[FishVoiceReference(**dict(row)) for row in rows], total=total, page=page, page_size=page_size)

    def delete(self, identifier: str) -> FishVoiceReference:
        with self._connection() as connection:
            saved = self._get(connection, identifier)
            connection.execute("DELETE FROM fish_voices WHERE id = ?", (identifier,))
        return saved
