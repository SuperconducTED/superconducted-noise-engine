"""Filesystem persistence for calibration snapshots.

Layout::

    data/calibration/{backend}/{YYYYMMDDTHHMMSSffffff}Z.json

Race-safe writes: we open the FINAL filename with
``os.O_WRONLY | os.O_CREAT | os.O_EXCL``. Concurrent writers see
:class:`FileExistsError` and skip cleanly. No tmp-file rename — the OS
guarantees the open-or-fail semantics on both POSIX and Windows.

Filename format is reversibly parseable. Decode with::

    datetime.strptime(stem, "%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc)
"""

from __future__ import annotations

import contextlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from ..types import CalibrationSnapshot

_FILENAME_FORMAT = "%Y%m%dT%H%M%S%fZ"


class _SnapshotJSONEncoder(json.JSONEncoder):
    """Encoder that handles datetime, complex, and numpy scalar/array types."""

    def default(self, o: Any) -> Any:
        if isinstance(o, datetime):
            ts = o if o.tzinfo is not None else o.replace(tzinfo=UTC)
            return ts.astimezone(UTC).isoformat()
        if isinstance(o, complex):
            return {"__complex__": [o.real, o.imag]}
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return super().default(o)


def _decode_filename_stem(stem: str) -> datetime:
    """Reverse of :meth:`CalibrationSnapshot.storage_filename`.

    Raises :class:`ValueError` if ``stem`` does not match the expected
    ``YYYYMMDDTHHMMSSffffffZ`` shape.
    """
    return datetime.strptime(stem, _FILENAME_FORMAT).replace(tzinfo=UTC)


class CalibrationStorage:
    """Filesystem-backed snapshot store, keyed by ``(backend, UTC timestamp)``."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, backend: str, timestamp: datetime) -> Path:
        ts = timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=UTC)
        ts = ts.astimezone(UTC)
        return self.root / backend / f"{ts.strftime(_FILENAME_FORMAT)}.json"

    def save_if_new(self, snapshot: CalibrationSnapshot) -> bool:
        """Atomically persist ``snapshot`` if no record for this key exists.

        Returns ``True`` if the file was written, ``False`` if a snapshot for
        this ``(backend, timestamp)`` pair already exists on disk.
        """
        path = self.path_for(snapshot.backend, snapshot.timestamp)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {
                "backend": snapshot.backend,
                "timestamp": snapshot.timestamp.isoformat(),
                "schema_version": snapshot.schema_version,
                "properties": snapshot.properties,
                "target": snapshot.target,
                "configuration": snapshot.configuration,
            },
            cls=_SnapshotJSONEncoder,
            indent=2,
            sort_keys=True,
        )
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            return False
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
        except BaseException:
            with contextlib.suppress(FileNotFoundError):
                path.unlink()
            raise
        return True

    def load(self, backend: str, timestamp: datetime) -> CalibrationSnapshot:
        """Read and deserialize a single snapshot.

        The on-disk timestamp is taken from the filename (UTC) for safety;
        the JSON body's ``timestamp`` field is informational only.
        """
        path = self.path_for(backend, timestamp)
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        parsed_ts = _decode_filename_stem(path.stem)
        return CalibrationSnapshot(
            backend=str(data["backend"]),
            timestamp=parsed_ts,
            schema_version=str(data["schema_version"]),
            properties=dict(data["properties"]),
            target=data.get("target"),
            configuration=data.get("configuration"),
        )

    def list_timestamps(self, backend: str) -> list[datetime]:
        """Return all archived UTC timestamps for ``backend`` in ascending order.

        Returns ``[]`` if the backend directory does not exist. Files with
        unparseable names are silently skipped.
        """
        backend_dir = self.root / backend
        if not backend_dir.exists():
            return []
        timestamps: list[datetime] = []
        for p in backend_dir.glob("*.json"):
            try:
                timestamps.append(_decode_filename_stem(p.stem))
            except ValueError:
                continue
        timestamps.sort()
        return timestamps
