"""Celery task for end-to-end ontology generation.

Orchestrates document parsing, LLM-based entity/property extraction,
graph construction in Apache AGE, provenance logging, SHACL validation,
and version snapshotting.

Celery workers are synchronous, so this module uses a dedicated sync
SQLAlchemy engine and wraps async operations with ``asyncio.run()``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
from datetime import datetime, timezone
from uuid import UUID

import redis

from app.config import get_settings
from app.tasks import celery_app

logger = logging.getLogger(__name__)

settings = get_settings()


# ---------------------------------------------------------------------------
# Redis helper for broadcasting progress to WebSocket subscribers
# ---------------------------------------------------------------------------

def _publish_progress(
    ontology_id: str,
    stage: str,
    progress: int,
    message: str = "",
) -> None:
    """Publish a progress event via Redis pub/sub.

    The WebSocket layer subscribes to ``ontology:{id}:progress`` channels.
    """
    try:
        r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        payload = json.dumps(
            {
                "ontology_id": ontology_id,
                "stage": stage,
                "progress": progress,
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        r.publish(f"ontology:{ontology_id}:progress", payload)
        r.close()
    except Exception as exc:
        logger.debug("Failed to publish progress: %s", exc)


# ---------------------------------------------------------------------------
# Helpers to run async code inside Celery's sync worker
# ---------------------------------------------------------------------------

def _run_async(coro):
    """Run an async coroutine in a new event loop (safe for Celery workers)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already running (shouldn't happen in Celery), create a new loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Main Celery task
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    name="app.tasks.processing.process_ontology_task",
    max_retries=1,
    acks_late=True,
)
def process_ontology_task(self, ontology_id: str) -> dict:
    """Process all pending documents for an ontology and build the graph.

    Steps:
        1. Set ontology status to ``processing``.
        2. Parse and chunk each pending document.
        3. Extract entities and properties from each chunk via LLM.
        4. Assemble the full ontology via LLM.
        5. Populate the Apache AGE graph.
        6. Log provenance for each LLM interaction.
        7. Run SHACL validation.
        8. Create an initial version snapshot.
        9. Set ontology status to ``ready``.

    On failure, the ontology status is set to ``error`` and the exception
    is logged.

    Args:
        ontology_id: String UUID of the ontology to process.

    Returns:
        Dict with processing summary.
    """
    logger.info("Starting processing for ontology %s", ontology_id)
    _publish_progress(ontology_id, "started", 0, "Processing started")

    try:
        result = _run_async(_process_ontology_async(ontology_id))
        return result
    except Exception as exc:
        logger.error(
            "Processing failed for ontology %s: %s\n%s",
            ontology_id,
            exc,
            traceback.format_exc(),
        )
        _run_async(_set_ontology_error(ontology_id, str(exc)))
        _publish_progress(ontology_id, "error", 0, str(exc))
        raise


async def _process_ontology_async(ontology_id: str) -> dict:
    """Async implementation of the processing pipeline."""
    from sqlalchemy import select

    from app.database import get_db
    from app.models.ontology import ConceptProvenance, Document, Ontology
    from app.services.document_service import chunk_text, parse_document
    from app.services.graph_service import GraphService
    from app.services.llm_service import LLMClient
    from app.services.ontology_service import create_version
    from app.services.validation_service import validate_ontology

    oid = UUID(ontology_id)
    llm = LLMClient()

    try:
        async for session in get_db():
            # -------------------------------------------------------
            # 1. Set status to "processing"
            # -------------------------------------------------------
            result = await session.execute(
                select(Ontology).where(Ontology.id == oid)
            )
            ontology = result.scalar_one_or_none()
            if ontology is None:
                raise ValueError(f"Ontology {ontology_id} not found")

            ontology.status = "processing"
            await session.commit()

            _publish_progress(ontology_id, "processing", 5, "Loading documents")

            # -------------------------------------------------------
            # 2. Gather pending documents
            # -------------------------------------------------------
            doc_result = await session.execute(
                select(Document).where(
                    Document.ontology_id == oid,
                    Document.status == "pending",
                )
            )
            documents = list(doc_result.scalars().all())

            if not documents:
                logger.warning("No pending documents for ontology %s", ontology_id)

            all_entities: list[dict] = []
            all_properties: list[dict] = []
            total_docs = len(documents) if documents else 1

            # -------------------------------------------------------
            # 3. Parse, chunk, and extract from each document
            # -------------------------------------------------------
            for doc_idx, doc in enumerate(documents):
                doc_progress_base = 10 + (doc_idx / total_docs) * 60

                _publish_progress(
                    ontology_id,
                    "parsing",
                    doc_progress_base,
                    f"Parsing document: {doc.filename}",
                )

                try:
                    # 3a. Parse document text
                    text = parse_document(doc.file_path, doc.content_type)

                    # 3b. Chunk text
                    chunks = chunk_text(text, chunk_size=4000, overlap=200)

                    _publish_progress(
                        ontology_id,
                        "extracting",
                        doc_progress_base + 10,
                        f"Extracting from {len(chunks)} chunks ({doc.filename})",
                    )

                    # 3c. Extract entities from each chunk
                    doc_entities: list[dict] = []
                    for chunk_idx, chunk in enumerate(chunks):
                        chunk_entities = await llm.extract_entities(
                            text=chunk,
                            domain_context=ontology.description or "",
                        )
                        doc_entities.extend(chunk_entities)

                        # Log provenance
                        for entity in chunk_entities:
                            provenance = ConceptProvenance(
                                ontology_id=oid,
                                concept_uri=entity.get("uri", ""),
                                document_id=doc.id,
                                prompt_text=f"extract_entities chunk {chunk_idx + 1}/{len(chunks)}",
                                response_text=entity,
                                extracted_data=entity,
                            )
                            session.add(provenance)

                    # 3d. Extract properties
                    doc_properties: list[dict] = []
                    if doc_entities:
                        for chunk_idx, chunk in enumerate(chunks):
                            chunk_properties = await llm.extract_properties(
                                text=chunk,
                                entities=doc_entities,
                            )
                            doc_properties.extend(chunk_properties)

                            # Log provenance for properties
                            for prop in chunk_properties:
                                provenance = ConceptProvenance(
                                    ontology_id=oid,
                                    concept_uri=prop.get("uri", ""),
                                    document_id=doc.id,
                                    prompt_text=f"extract_properties chunk {chunk_idx + 1}/{len(chunks)}",
                                    response_text=prop,
                                    extracted_data=prop,
                                )
                                session.add(provenance)

                    all_entities.extend(doc_entities)
                    all_properties.extend(doc_properties)

                    # 3e. Mark document as processed
                    doc.status = "processed"
                    await session.commit()

                except Exception as doc_exc:
                    logger.error(
                        "Error processing document %s: %s",
                        doc.filename,
                        doc_exc,
                        exc_info=True,
                    )
                    doc.status = "error"
                    doc.error_message = str(doc_exc)[:1000]
                    await session.commit()

            # -------------------------------------------------------
            # 4. Assemble full ontology via LLM
            # -------------------------------------------------------
            _publish_progress(
                ontology_id, "assembling", 75, "Assembling ontology"
            )

            existing_classes = await GraphService.get_class_uris(session, oid)
            assembled = await llm.assemble_ontology(
                entities=all_entities,
                properties=all_properties,
                existing_classes=existing_classes,
            )

            # Log assembly provenance
            assembly_provenance = ConceptProvenance(
                ontology_id=oid,
                concept_uri="_assembly",
                document_id=documents[0].id if documents else None,
                prompt_text="assemble_ontology",
                response_text=assembled,
                extracted_data=assembled,
            )
            session.add(assembly_provenance)

            # -------------------------------------------------------
            # 5. Build graph in AGE
            # -------------------------------------------------------
            _publish_progress(
                ontology_id, "building_graph", 85, "Building knowledge graph"
            )

            # Ensure graph exists
            try:
                await GraphService.create_graph(session, oid)
            except Exception:
                pass  # Graph may already exist

            await GraphService.build_from_llm_output(session, oid, assembled)
            await session.commit()

            # -------------------------------------------------------
            # 6. Run SHACL validation
            # -------------------------------------------------------
            _publish_progress(
                ontology_id, "validating", 92, "Running SHACL validation"
            )

            validation_result = await validate_ontology(
                session, oid, namespace_uri=ontology.namespace_uri,
            )

            if not validation_result.conforms:
                logger.warning(
                    "Ontology %s has %d SHACL violations",
                    ontology_id,
                    len(validation_result.violations),
                )

            # -------------------------------------------------------
            # 7. Create initial version snapshot
            # -------------------------------------------------------
            _publish_progress(
                ontology_id, "snapshot", 96, "Creating version snapshot"
            )

            await create_version(
                session, oid, description="Initial generated version",
            )

            # -------------------------------------------------------
            # 8. Set status to "ready"
            # -------------------------------------------------------
            ontology.status = "ready"
            await session.commit()

            _publish_progress(
                ontology_id, "complete", 100, "Processing complete"
            )

            logger.info("Ontology %s processing complete", ontology_id)

            return {
                "ontology_id": ontology_id,
                "status": "ready",
                "entities_extracted": len(all_entities),
                "properties_extracted": len(all_properties),
                "classes_assembled": len(assembled.get("classes", [])),
                "validation_conforms": validation_result.conforms,
                "violations": len(validation_result.violations),
            }
    finally:
        await llm.close()


async def _set_ontology_error(ontology_id: str, error_message: str) -> None:
    """Set ontology status to error."""
    from sqlalchemy import select

    from app.database import get_db
    from app.models.ontology import Ontology

    oid = UUID(ontology_id)
    async for session in get_db():
        result = await session.execute(
            select(Ontology).where(Ontology.id == oid)
        )
        ontology = result.scalar_one_or_none()
        if ontology:
            ontology.status = "error"
            await session.commit()
