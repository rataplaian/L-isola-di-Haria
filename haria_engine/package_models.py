"""Modelli immutabili per i pacchetti narrativi completi."""

from __future__ import annotations

from dataclasses import dataclass

from .models import FileSorgente
from .world_state import EntitaImportata


@dataclass(frozen=True, slots=True)
class DocumentoCanonico:
    world_id: str
    document_id: str
    document_type: str
    title: str
    relative_path: str
    content: str
    sort_order: int
    metadata: dict[str, object]
    sha256: str


@dataclass(frozen=True, slots=True)
class MediaCanonico:
    world_id: str
    media_id: str
    relative_path: str
    media_type: str
    mime_type: str
    sha256: str
    title: str
    alt_text: str
    entity_id: str | None
    sort_order: int
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class PacchettoMondo:
    world_id: str
    title: str
    language: str
    scenario: str
    narrative_settings: dict[str, str]
    source_files: tuple[FileSorgente, ...]
    entities: tuple[EntitaImportata, ...]
    documents: tuple[DocumentoCanonico, ...]
    media: tuple[MediaCanonico, ...]
    complete_format: bool

