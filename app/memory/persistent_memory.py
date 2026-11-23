"""PlantGuard Persistent Memory Engine for M3.

Provides durable SQLite-backed storage for:
1. Stable asset facts & parameters (persisted independently of conversation transcripts)
2. Maintenance event history (timestamped, asset-tagged, work-order linked)
3. Procedural memory (updatable SOP & LOTO steps)
4. Session working memory with token/message budget trimming
5. Multi-tenant / asset isolation to prevent cross-identity leakage.
"""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.config.settings import get_settings


class AssetFact(BaseModel):
    fact_id: Optional[int] = None
    asset_tag: str
    fact_key: str
    fact_value: str
    updated_at: str
    updated_by: str = "system"
    version: int = 1


class MaintenanceHistoryRecord(BaseModel):
    record_id: Optional[int] = None
    asset_tag: str
    work_order_id: Optional[str] = None
    event_timestamp: str
    event_type: str  # "corrective", "preventive", "bearing_replacement", etc.
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)
    identity_id: str = "default_user"


class ProceduralStep(BaseModel):
    procedure_name: str
    asset_code: Optional[str] = None
    step_number: int
    instruction: str
    safety_hazard: Optional[str] = None
    requires_loto: bool = False


class PersistentMemoryManager:
    """
    SQLite-backed memory manager surviving application restart.
    """

    def __init__(self, db_path: Optional[Path | str] = None):
        settings = get_settings()
        if db_path is None:
            # Use path from settings or local db
            db_url = settings.MEMORY_DATABASE_URL
            if db_url.startswith("sqlite:///"):
                db_name = db_url.replace("sqlite:///", "")
                self.db_path = str(settings.PROJECT_ROOT / db_name)
            else:
                self.db_path = ":memory:"
        else:
            self.db_path = str(db_path)

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create database tables with indices."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Stable asset facts table (supports versioning and supersession - T1, T7)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS asset_facts (
                    fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_tag TEXT NOT NULL,
                    fact_key TEXT NOT NULL,
                    fact_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    version INTEGER DEFAULT 1,
                    identity_id TEXT DEFAULT 'default_user',
                    UNIQUE(asset_tag, fact_key, identity_id)
                )
            """)

            # Historical maintenance events table (T2, T4)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS maintenance_history (
                    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_tag TEXT NOT NULL,
                    work_order_id TEXT,
                    event_timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    details_json TEXT,
                    identity_id TEXT DEFAULT 'default_user'
                )
            """)

            # Procedural memory (SOPs, LOTO steps - T3, T6)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS procedural_memory (
                    procedure_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    procedure_name TEXT NOT NULL,
                    asset_code TEXT,
                    step_number INTEGER NOT NULL,
                    instruction TEXT NOT NULL,
                    safety_hazard TEXT,
                    requires_loto BOOLEAN DEFAULT 0,
                    UNIQUE(procedure_name, step_number)
                )
            """)

            # Working session context
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_messages (
                    msg_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    identity_id TEXT DEFAULT 'default_user'
                )
            """)
            conn.commit()

    # ── Stable Asset Facts (T1, T5, T7) ──

    def store_fact(
        self,
        asset_tag: str,
        fact_key: str,
        fact_value: str,
        updated_by: str = "system",
        identity_id: str = "default_user",
    ) -> AssetFact:
        """Store or update a stable asset fact. Newer fact supersedes older fact (T7)."""
        asset_tag = asset_tag.strip().upper()
        now_iso = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Check existing version
            cursor.execute(
                "SELECT version FROM asset_facts WHERE asset_tag = ? AND fact_key = ? AND identity_id = ?",
                (asset_tag, fact_key, identity_id),
            )
            row = cursor.fetchone()
            new_version = (row["version"] + 1) if row else 1

            cursor.execute("""
                INSERT INTO asset_facts (asset_tag, fact_key, fact_value, updated_at, updated_by, version, identity_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asset_tag, fact_key, identity_id) DO UPDATE SET
                    fact_value = excluded.fact_value,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by,
                    version = excluded.version
            """, (asset_tag, fact_key, fact_value, now_iso, updated_by, new_version, identity_id))
            conn.commit()

        return AssetFact(
            asset_tag=asset_tag,
            fact_key=fact_key,
            fact_value=fact_value,
            updated_at=now_iso,
            updated_by=updated_by,
            version=new_version,
        )

    def get_fact(
        self,
        asset_tag: str,
        fact_key: str,
        identity_id: str = "default_user",
    ) -> Optional[AssetFact]:
        """Retrieve a stable fact with identity isolation (T8)."""
        asset_tag = asset_tag.strip().upper()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM asset_facts WHERE asset_tag = ? AND fact_key = ? AND identity_id = ?",
                (asset_tag, fact_key, identity_id),
            )
            row = cursor.fetchone()
            if row:
                return AssetFact(
                    fact_id=row["fact_id"],
                    asset_tag=row["asset_tag"],
                    fact_key=row["fact_key"],
                    fact_value=row["fact_value"],
                    updated_at=row["updated_at"],
                    updated_by=row["updated_by"],
                    version=row["version"],
                )
            return None

    def list_facts_for_asset(
        self,
        asset_tag: str,
        identity_id: str = "default_user",
    ) -> List[AssetFact]:
        asset_tag = asset_tag.strip().upper()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM asset_facts WHERE asset_tag = ? AND identity_id = ? ORDER BY fact_key",
                (asset_tag, identity_id),
            )
            return [
                AssetFact(
                    fact_id=r["fact_id"],
                    asset_tag=r["asset_tag"],
                    fact_key=r["fact_key"],
                    fact_value=r["fact_value"],
                    updated_at=r["updated_at"],
                    updated_by=r["updated_by"],
                    version=r["version"],
                )
                for r in cursor.fetchall()
            ]

    # ── Maintenance History Memory (T2, T4) ──

    def record_maintenance_event(
        self,
        asset_tag: str,
        event_type: str,
        summary: str,
        work_order_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        identity_id: str = "default_user",
        timestamp: Optional[str] = None,
    ) -> MaintenanceHistoryRecord:
        asset_tag = asset_tag.strip().upper()
        ts = timestamp or datetime.now().isoformat()
        details_json = json.dumps(details or {})

        with self._get_connection() as conn:
            cursor = conn.cursor()
            if work_order_id:
                cursor.execute(
                    "SELECT * FROM maintenance_history WHERE work_order_id = ? AND identity_id = ? ORDER BY record_id LIMIT 1",
                    (work_order_id, identity_id),
                )
                existing = cursor.fetchone()
                if existing:
                    return MaintenanceHistoryRecord(
                        record_id=existing["record_id"],
                        asset_tag=existing["asset_tag"],
                        work_order_id=existing["work_order_id"],
                        event_timestamp=existing["event_timestamp"],
                        event_type=existing["event_type"],
                        summary=existing["summary"],
                        details=json.loads(existing["details_json"] or "{}"),
                        identity_id=existing["identity_id"],
                    )
            cursor.execute("""
                INSERT INTO maintenance_history (asset_tag, work_order_id, event_timestamp, event_type, summary, details_json, identity_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (asset_tag, work_order_id, ts, event_type, summary, details_json, identity_id))
            rec_id = cursor.lastrowid
            conn.commit()

        return MaintenanceHistoryRecord(
            record_id=rec_id,
            asset_tag=asset_tag,
            work_order_id=work_order_id,
            event_timestamp=ts,
            event_type=event_type,
            summary=summary,
            details=details or {},
            identity_id=identity_id,
        )

    def get_recent_history(
        self,
        asset_tag: str,
        limit: int = 5,
        identity_id: str = "default_user",
    ) -> List[MaintenanceHistoryRecord]:
        asset_tag = asset_tag.strip().upper()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM maintenance_history
                WHERE asset_tag = ? AND identity_id = ?
                ORDER BY event_timestamp DESC LIMIT ?
            """, (asset_tag, identity_id, limit))
            records = []
            for r in cursor.fetchall():
                records.append(
                    MaintenanceHistoryRecord(
                        record_id=r["record_id"],
                        asset_tag=r["asset_tag"],
                        work_order_id=r["work_order_id"],
                        event_timestamp=r["event_timestamp"],
                        event_type=r["event_type"],
                        summary=r["summary"],
                        details=json.loads(r["details_json"] or "{}"),
                        identity_id=r["identity_id"],
                    )
                )
            return records

    # ── Procedural Memory (T3, T6) ──

    def store_procedure_step(
        self,
        procedure_name: str,
        step_number: int,
        instruction: str,
        asset_code: Optional[str] = None,
        safety_hazard: Optional[str] = None,
        requires_loto: bool = False,
    ) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO procedural_memory (procedure_name, asset_code, step_number, instruction, safety_hazard, requires_loto)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(procedure_name, step_number) DO UPDATE SET
                    instruction = excluded.instruction,
                    safety_hazard = excluded.safety_hazard,
                    requires_loto = excluded.requires_loto
            """, (procedure_name, asset_code, step_number, instruction, safety_hazard, int(requires_loto)))
            conn.commit()

    def get_procedure_steps(self, procedure_name: str) -> List[ProceduralStep]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM procedural_memory WHERE procedure_name = ? ORDER BY step_number ASC",
                (procedure_name,),
            )
            return [
                ProceduralStep(
                    procedure_name=r["procedure_name"],
                    asset_code=r["asset_code"],
                    step_number=r["step_number"],
                    instruction=r["instruction"],
                    safety_hazard=r["safety_hazard"],
                    requires_loto=bool(r["requires_loto"]),
                )
                for r in cursor.fetchall()
            ]

    # ── Working Memory & Trim Budget (T9) ──

    def add_session_message(
        self,
        session_id: str,
        role: str,
        content: str,
        identity_id: str = "default_user",
        max_history: int = 10,
    ) -> None:
        """Add message to session context and apply rolling trim budget."""
        now_iso = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO session_messages (session_id, role, content, timestamp, identity_id)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, role, content, now_iso, identity_id))

            # Trim older messages exceeding budget
            cursor.execute("""
                DELETE FROM session_messages
                WHERE session_id = ? AND msg_id NOT IN (
                    SELECT msg_id FROM session_messages
                    WHERE session_id = ?
                    ORDER BY msg_id DESC LIMIT ?
                )
            """, (session_id, session_id, max_history))
            conn.commit()

    def get_session_history(self, session_id: str, identity_id: str = "default_user") -> List[Dict[str, str]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role, content FROM session_messages
                WHERE session_id = ? AND identity_id = ?
                ORDER BY msg_id ASC
            """, (session_id, identity_id))
            return [{"role": r["role"], "content": r["content"]} for r in cursor.fetchall()]

    # ── Semantic Vector Document Index (M3 Advanced Item) ──

    def init_semantic_index(self, corpus_chunks: Optional[List[Any]] = None) -> None:
        """Initialize semantic vector index for manuals and SOPs with rich metadata."""
        from app.rag.engine import DenseVectorIndex, DocumentChunk
        self._semantic_index = DenseVectorIndex()
        if corpus_chunks:
            self._semantic_index.fit(corpus_chunks)
        else:
            settings = get_settings()
            md_dir = settings.DATA_DIR / "corpus" / "markdown"
            chunks = []
            if md_dir.exists():
                import re
                for file_path in sorted(md_dir.glob("*.md")):
                    slug = file_path.stem
                    text = file_path.read_text(encoding="utf-8")
                    asset_code = slug.replace("manual-", "").upper() if slug.startswith("manual-") else None
                    sections = re.split(r"\n(?=#{1,3}\s+)", text)
                    for idx, section_text in enumerate(sections):
                        section_text = section_text.strip()
                        if not section_text:
                            continue
                        first_line = section_text.splitlines()[0]
                        sec_title = first_line.lstrip("#").strip() if first_line.startswith("#") else f"Section {idx+1}"
                        chunks.append(
                            DocumentChunk(
                                chunk_id=f"{slug}-sec{idx+1:02d}",
                                doc_slug=slug,
                                doc_title=slug.replace("-", " ").title(),
                                section=sec_title,
                                asset_code=asset_code,
                                content=section_text,
                                char_count=len(section_text),
                            )
                        )

            # Ingest PDF manuals
            pdf_dir = settings.DATA_DIR / "corpus" / "pdf"
            if pdf_dir.exists():
                try:
                    import pypdf
                    for pdf_file in sorted(pdf_dir.glob("*.pdf")):
                        slug = pdf_file.stem
                        reader = pypdf.PdfReader(str(pdf_file))
                        asset_code = slug.replace("manual-", "").upper() if slug.startswith("manual-") else None
                        for page_idx, page in enumerate(reader.pages):
                            page_text = (page.extract_text() or "").strip()
                            if not page_text:
                                continue
                            chunks.append(
                                DocumentChunk(
                                    chunk_id=f"{slug}-pdf-p{page_idx+1:02d}",
                                    doc_slug=slug,
                                    doc_title=f"{slug.replace('-', ' ').title()} (PDF)",
                                    section=f"Page {page_idx+1}",
                                    asset_code=asset_code,
                                    content=page_text,
                                    char_count=len(page_text),
                                )
                            )
                except Exception as e:
                    pass
            self._semantic_index.fit(chunks)

    def search_semantic(self, query: str, top_k: int = 5, asset_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """Semantic vector retrieval over indexed manuals and SOPs with metadata filtering."""
        if not hasattr(self, "_semantic_index") or self._semantic_index is None:
            self.init_semantic_index()

        matches = self._semantic_index.search(query, top_k=top_k * 2)
        filtered = []
        for chunk, score in matches:
            if asset_code and chunk.asset_code and chunk.asset_code != asset_code:
                continue
            filtered.append({
                "chunk_id": chunk.chunk_id,
                "doc_slug": chunk.doc_slug,
                "doc_title": chunk.doc_title,
                "section": chunk.section,
                "asset_code": chunk.asset_code,
                "score": round(score, 4),
                "preview": chunk.content[:200],
            })
            if len(filtered) >= top_k:
                break
        return filtered

    # ── Privacy Retention & Deletion Controls (M3 Advanced Item) ──

    def purge_identity_data(self, identity_id: str) -> Dict[str, int]:
        """Purge all stored facts, history, and session messages for an identity (GDPR/compliance)."""
        counts = {}
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM asset_facts WHERE identity_id = ?", (identity_id,))
            counts["deleted_facts"] = cursor.rowcount

            cursor.execute("DELETE FROM maintenance_history WHERE identity_id = ?", (identity_id,))
            counts["deleted_history"] = cursor.rowcount

            cursor.execute("DELETE FROM session_messages WHERE identity_id = ?", (identity_id,))
            counts["deleted_messages"] = cursor.rowcount
            conn.commit()
        return counts

    def summarize_and_trim_session(self, session_id: str, token_budget: int = 500) -> str:
        """Create a rolling summary of older messages and trim history to fit token budget."""
        history = self.get_session_history(session_id)
        if not history:
            return ""

        total_words = sum(len(m["content"].split()) for m in history)
        approx_tokens = int(total_words * 1.3)

        if approx_tokens > token_budget:
            # Create rolling summary of early messages
            early_msgs = history[: len(history) // 2]
            summary_text = "Prior conversation summary: " + "; ".join(f"{m['role']}: {m['content'][:60]}..." for m in early_msgs)
            # Retain only recent messages
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM session_messages
                    WHERE session_id = ? AND msg_id IN (
                        SELECT msg_id FROM session_messages WHERE session_id = ? ORDER BY msg_id ASC LIMIT ?
                    )
                """, (session_id, session_id, len(early_msgs)))
                conn.commit()
            return summary_text
        return ""

    def close(self) -> None:
        """Close connections."""
        pass
