"""Validation service for ontology SHACL conformance checking.

Loads base SHACL shapes from ``backend/shapes.ttl``, exports the ontology as
Turtle, and runs pyshacl validation.  Results are returned as a structured
``ValidationResult``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.export_service import export_ontology

logger = logging.getLogger(__name__)

# Path to the base SHACL shapes file (relative to the backend/ directory)
_SHAPES_PATH = Path(__file__).resolve().parent.parent.parent / "shapes.ttl"


# ---------------------------------------------------------------------------
# Result data class
# ---------------------------------------------------------------------------

@dataclass
class ValidationViolation:
    """A single SHACL validation violation."""

    severity: str  # "Violation", "Warning", "Info"
    focus_node: str
    path: str
    message: str
    source_shape: str = ""


@dataclass
class ValidationResult:
    """Aggregated result of a SHACL validation run."""

    conforms: bool = True
    violations: list[ValidationViolation] = field(default_factory=list)
    warnings: list[ValidationViolation] = field(default_factory=list)
    info_messages: list[str] = field(default_factory=list)
    raw_report: str = ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def validate_ontology(
    session: AsyncSession,
    ontology_id: UUID,
    namespace_uri: str = "http://example.org/ontology#",
) -> ValidationResult:
    """Validate an ontology graph against SHACL shapes.

    1. Export the ontology as Turtle.
    2. Load SHACL shapes from ``backend/shapes.ttl`` (if available).
    3. Run ``pyshacl.validate()`` and parse the results.

    If the shapes file is missing, the function returns a result with an
    informational message and ``conforms=True`` (no shapes to violate).

    Args:
        session: Async database session.
        ontology_id: UUID of the ontology to validate.
        namespace_uri: Base namespace URI for the ontology.

    Returns:
        A :class:`ValidationResult` with conformance status and any violations.
    """
    result = ValidationResult()

    # ------------------------------------------------------------------
    # 1. Export ontology as Turtle
    # ------------------------------------------------------------------
    try:
        turtle_data = await export_ontology(
            session, ontology_id, fmt="ttl", namespace_uri=namespace_uri,
        )
    except Exception as exc:
        logger.error("Failed to export ontology %s for validation: %s", ontology_id, exc)
        result.conforms = False
        result.info_messages.append(f"Export failed: {exc}")
        return result

    if not turtle_data or not str(turtle_data).strip():
        result.info_messages.append("Ontology graph is empty; nothing to validate.")
        return result

    # ------------------------------------------------------------------
    # 2. Load SHACL shapes
    # ------------------------------------------------------------------
    if not _SHAPES_PATH.exists():
        logger.warning(
            "SHACL shapes file not found at %s; skipping validation",
            _SHAPES_PATH,
        )
        result.info_messages.append(
            f"SHACL shapes file not found at {_SHAPES_PATH}. "
            "Validation skipped."
        )
        return result

    shapes_ttl = _SHAPES_PATH.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # 3. Run pyshacl
    # ------------------------------------------------------------------
    try:
        import pyshacl
        from rdflib import Graph as RdfGraph

        data_graph = RdfGraph()
        data_graph.parse(data=str(turtle_data), format="turtle")

        shapes_graph = RdfGraph()
        shapes_graph.parse(data=shapes_ttl, format="turtle")

        conforms, report_graph, report_text = pyshacl.validate(
            data_graph=data_graph,
            shacl_graph=shapes_graph,
            inference="rdfs",
            abort_on_first=False,
            meta_shacl=False,
            advanced=True,
        )

        result.conforms = conforms
        result.raw_report = report_text

        # Parse individual violations from the report graph
        _parse_report_graph(report_graph, result)

    except ImportError:
        logger.error("pyshacl is not installed; cannot validate ontology")
        result.info_messages.append(
            "pyshacl library not installed. Install with: pip install pyshacl"
        )
    except Exception as exc:
        logger.error("SHACL validation failed: %s", exc, exc_info=True)
        result.conforms = False
        result.info_messages.append(f"Validation error: {exc}")

    logger.info(
        "Validation for ontology %s: conforms=%s, violations=%d, warnings=%d",
        ontology_id,
        result.conforms,
        len(result.violations),
        len(result.warnings),
    )
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_report_graph(report_graph, result: ValidationResult) -> None:
    """Extract structured violations from the pyshacl report graph."""
    from rdflib import SH, Literal, URIRef  # type: ignore[attr-defined]
    from rdflib.namespace import RDF

    SH_NS = "http://www.w3.org/ns/shacl#"

    # Find all ValidationResult nodes
    for report_node in report_graph.subjects(
        RDF.type, URIRef(f"{SH_NS}ValidationResult")
    ):
        severity_raw = ""
        focus_node = ""
        path = ""
        message = ""
        source_shape = ""

        for pred, obj in report_graph.predicate_objects(report_node):
            pred_str = str(pred)
            if pred_str == f"{SH_NS}resultSeverity":
                severity_raw = str(obj).split("#")[-1] if "#" in str(obj) else str(obj)
            elif pred_str == f"{SH_NS}focusNode":
                focus_node = str(obj)
            elif pred_str == f"{SH_NS}resultPath":
                path = str(obj)
            elif pred_str == f"{SH_NS}resultMessage":
                message = str(obj)
            elif pred_str == f"{SH_NS}sourceShape":
                source_shape = str(obj)

        violation = ValidationViolation(
            severity=severity_raw,
            focus_node=focus_node,
            path=path,
            message=message,
            source_shape=source_shape,
        )

        if severity_raw == "Violation":
            result.violations.append(violation)
        elif severity_raw == "Warning":
            result.warnings.append(violation)
        else:
            result.info_messages.append(message or f"Info from {focus_node}")
