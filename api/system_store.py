"""Persistent JSON storage for AI system records."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import shutil
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ingestion.models import slugify_fragment

AnalysisStatus = Literal["new", "analyzed", "error"]


class StoredAISystem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    system_type: str = Field(min_length=1)
    catalog: str = Field(default="Default", min_length=1)
    level_of_risk: str | None = None
    confidence: int | None = Field(default=None, ge=0, le=100)
    analysis_summary: str | None = None
    analysis_status: AnalysisStatus = "new"
    analysis_error: str | None = None
    analysis_citations: list[str] = Field(default_factory=list)
    last_user_role: str | None = None
    last_provider: str | None = None
    last_model: str | None = None
    last_analyzed_at: str | None = None
    created_at: str
    updated_at: str


class AISystemJsonStore:
    """Read and write AI system records from a single JSON file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self._max_backups = 5

    def list_systems(self) -> list[StoredAISystem]:
        return sorted(self._load(), key=lambda item: item.updated_at, reverse=True)

    def get_system(self, system_id: str) -> StoredAISystem | None:
        for system in self._load():
            if system.id == system_id:
                return system
        return None

    def upsert_system(
        self,
        *,
        name: str,
        description: str,
        system_type: str,
        catalog: str = "Default",
    ) -> tuple[StoredAISystem, bool]:
        systems = self._load()
        normalized_name = slugify_fragment(name)
        now = _utc_now()
        catalog_value = _clean_catalog(catalog)
        normalized_catalog = _normalize_catalog(catalog_value)

        for index, system in enumerate(systems):
            if (
                slugify_fragment(system.name) != normalized_name
                or _normalize_catalog(system.catalog) != normalized_catalog
            ):
                continue

            payload = {
                "name": name.strip(),
                "description": description.strip(),
                "system_type": system_type.strip(),
                "catalog": catalog_value,
                "updated_at": now,
            }
            changed = (
                system.description.strip() != description.strip()
                or system.system_type.strip() != system_type.strip()
                or system.name.strip() != name.strip()
            )
            if changed:
                payload.update(
                    {
                        "level_of_risk": None,
                        "confidence": None,
                        "analysis_summary": None,
                        "analysis_status": "new",
                        "analysis_error": None,
                        "analysis_citations": [],
                        "last_user_role": None,
                        "last_provider": None,
                        "last_model": None,
                        "last_analyzed_at": None,
                    }
                )

            updated = system.model_copy(update=payload)
            systems[index] = updated
            self._save(systems)
            return updated, False

        system = StoredAISystem(
            id=self._make_id(name, systems),
            name=name.strip(),
            description=description.strip(),
            system_type=system_type.strip(),
            catalog=catalog_value,
            created_at=now,
            updated_at=now,
        )
        systems.append(system)
        self._save(systems)
        return system, True

    def update_system(
        self,
        system_id: str,
        *,
        name: str,
        description: str,
        system_type: str,
        catalog: str | None = None,
    ) -> StoredAISystem:
        systems = self._load()
        normalized_name = slugify_fragment(name)
        now = _utc_now()
        existing = next((system for system in systems if system.id == system_id), None)
        if existing is None:
            raise KeyError(f"Unknown AI system id: {system_id}")
        catalog_value = _clean_catalog(catalog) if catalog is not None else existing.catalog
        normalized_catalog = _normalize_catalog(catalog_value)
        for other in systems:
            if (
                other.id != system_id
                and slugify_fragment(other.name) == normalized_name
                and _normalize_catalog(other.catalog) == normalized_catalog
            ):
                raise ValueError(f'Another AI system already uses the name "{name.strip()}".')

        for index, system in enumerate(systems):
            if system.id != system_id:
                continue

            analysis_needs_reset = (
                system.description.strip() != description.strip()
                or system.system_type.strip() != system_type.strip()
            )
            payload = {
                "name": name.strip(),
                "description": description.strip(),
                "system_type": system_type.strip(),
                "catalog": catalog_value,
                "updated_at": now,
            }
            if analysis_needs_reset:
                payload.update(
                    {
                        "level_of_risk": None,
                        "confidence": None,
                        "analysis_summary": None,
                        "analysis_status": "new",
                        "analysis_error": None,
                        "analysis_citations": [],
                        "last_user_role": None,
                        "last_provider": None,
                        "last_model": None,
                        "last_analyzed_at": None,
                    }
                )

            updated = system.model_copy(update=payload)
            systems[index] = updated
            self._save(systems)
            return updated

        raise KeyError(f"Unknown AI system id: {system_id}")

    def update_analysis(
        self,
        system_id: str,
        *,
        level_of_risk: str | None,
        confidence: int | None,
        summary: str | None,
        citations: list[str],
        user_role: str | None,
        provider: str | None,
        model: str | None,
        status: AnalysisStatus,
        error: str | None = None,
    ) -> StoredAISystem:
        systems = self._load()
        now = _utc_now()
        for index, system in enumerate(systems):
            if system.id != system_id:
                continue

            updated = system.model_copy(
                update={
                    "level_of_risk": level_of_risk,
                    "confidence": confidence,
                    "analysis_summary": summary,
                    "analysis_status": status,
                    "analysis_error": error,
                    "analysis_citations": citations,
                    "last_user_role": user_role,
                    "last_provider": provider,
                    "last_model": model,
                    "last_analyzed_at": now if status == "analyzed" else system.last_analyzed_at,
                    "updated_at": now,
                }
            )
            systems[index] = updated
            self._save(systems)
            return updated
        raise KeyError(f"Unknown AI system id: {system_id}")

    def delete_system(self, system_id: str) -> bool:
        systems = self._load()
        remaining = [item for item in systems if item.id != system_id]
        if len(remaining) == len(systems):
            return False
        self._save(remaining)
        return True

    def _load(self) -> list[StoredAISystem]:
        with self._file_lock(exclusive=False):
            return self._load_unlocked()

    def _load_unlocked(self) -> list[StoredAISystem]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            recovered = self._try_recover_backup()
            if recovered is None:
                raise RuntimeError(f"Invalid AI system store JSON at {self.path}: {exc}") from exc
            raw = recovered
        if not isinstance(raw, list):
            raise RuntimeError(f"AI system store at {self.path} must contain a JSON array.")
        return [StoredAISystem.model_validate(item) for item in raw]

    def _save(self, systems: list[StoredAISystem]) -> None:
        with self._file_lock(exclusive=True):
            self._save_unlocked(systems)

    def _save_unlocked(self, systems: list[StoredAISystem]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [item.model_dump() for item in systems]
        serialized = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
        self._rotate_backups()
        self._atomic_write(serialized)

    def _make_id(self, name: str, systems: list[StoredAISystem]) -> str:
        base = slugify_fragment(name)
        existing_ids = {system.id for system in systems}
        if base not in existing_ids:
            return base
        suffix = 2
        while f"{base}_{suffix}" in existing_ids:
            suffix += 1
        return f"{base}_{suffix}"

    def import_systems(
        self,
        systems: list[StoredAISystem],
        *,
        mode: Literal["merge", "replace"] = "merge",
    ) -> dict[str, int]:
        deduped = self._dedupe_by_id(systems)
        with self._file_lock(exclusive=True):
            current = [] if mode == "replace" else self._load_unlocked()
            current_by_id = {system.id: system for system in current}
            imported = 0
            updated = 0
            for system in deduped:
                if system.id in current_by_id:
                    updated += 1
                else:
                    imported += 1
                current_by_id[system.id] = system
            merged = list(current_by_id.values())
            self._save_unlocked(merged)

        return {
            "total": len(deduped),
            "imported": imported,
            "updated": updated,
        }

    def _dedupe_by_id(self, systems: list[StoredAISystem]) -> list[StoredAISystem]:
        by_id: dict[str, StoredAISystem] = {}
        for system in systems:
            by_id[system.id] = system
        return list(by_id.values())

    @contextmanager
    def _file_lock(self, *, exclusive: bool) -> object:
        try:
            import fcntl
        except ImportError:
            yield
            return

        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._lock_path, "a+", encoding="utf-8") as lock_file:
            lock_mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            fcntl.flock(lock_file.fileno(), lock_mode)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _atomic_write(self, payload: str) -> None:
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, self.path)

    def _rotate_backups(self) -> None:
        if not self.path.exists():
            return
        for index in range(self._max_backups, 1, -1):
            src = self._backup_path(index - 1)
            dest = self._backup_path(index)
            if src.exists():
                shutil.copy2(src, dest)
        shutil.copy2(self.path, self._backup_path(1))

    def _backup_path(self, index: int) -> Path:
        return self.path.with_suffix(self.path.suffix + f".bak{index}")

    def _try_recover_backup(self) -> list[object] | None:
        for index in range(1, self._max_backups + 1):
            backup_path = self._backup_path(index)
            if not backup_path.exists():
                continue
            try:
                raw = json.loads(backup_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(raw, list):
                return raw
        return None


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _clean_catalog(value: str | None) -> str:
    cleaned = (value or "").strip()
    return cleaned or "Default"


def _normalize_catalog(value: str | None) -> str:
    return _clean_catalog(value).lower()
