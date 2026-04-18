"""Tests for ontology export to Turtle and JSON-LD formats."""

from __future__ import annotations

import json

import pytest

from app.services.export_service import _export_rdf, _export_json
from app.services.graph_service import GraphData


# ---------------------------------------------------------------------------
# Turtle export
# ---------------------------------------------------------------------------
def test_export_turtle(sample_graph_data: GraphData):
    """Exporting graph data as Turtle produces valid RDF containing expected URIs."""
    ttl_output = _export_rdf(
        sample_graph_data,
        fmt="ttl",
        namespace_uri="http://example.org/test#",
    )

    assert isinstance(ttl_output, str)
    assert len(ttl_output) > 0

    # The output should contain the class URIs and labels
    assert "Building" in ttl_output
    assert "Floor" in ttl_output

    # Turtle files contain triple-terminating periods
    assert "." in ttl_output


def test_export_turtle_empty_graph():
    """Exporting an empty graph produces a valid (possibly minimal) Turtle document."""
    empty_graph = GraphData(nodes=[], edges=[])
    ttl_output = _export_rdf(
        empty_graph,
        fmt="ttl",
        namespace_uri="http://example.org/empty#",
    )

    assert isinstance(ttl_output, str)


# ---------------------------------------------------------------------------
# JSON-LD export
# ---------------------------------------------------------------------------
def test_export_jsonld(sample_graph_data: GraphData):
    """Exporting graph data as JSON-LD produces valid JSON with RDF content."""
    jsonld_output = _export_rdf(
        sample_graph_data,
        fmt="jsonld",
        namespace_uri="http://example.org/test#",
    )

    assert isinstance(jsonld_output, str)

    # Must be valid JSON
    data = json.loads(jsonld_output)
    assert isinstance(data, (dict, list))

    # Verify our entities appear somewhere in the serialized output
    raw = json.dumps(data) if isinstance(data, dict) else json.dumps(data)
    assert "Building" in raw
    assert "Floor" in raw


def test_export_jsonld_empty_graph():
    """Exporting an empty graph produces valid JSON."""
    empty_graph = GraphData(nodes=[], edges=[])
    jsonld_output = _export_rdf(
        empty_graph,
        fmt="jsonld",
        namespace_uri="http://example.org/empty#",
    )

    assert isinstance(jsonld_output, str)
    data = json.loads(jsonld_output)
    assert isinstance(data, (dict, list))


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------
def test_export_json(sample_graph_data: GraphData):
    """Exporting graph data as JSON produces valid JSON with nodes and edges."""
    json_output = _export_json(sample_graph_data)

    assert isinstance(json_output, str)

    data = json.loads(json_output)
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1
    assert data["nodes"][0]["label"] == "Building"


def test_export_unsupported_format(sample_graph_data: GraphData):
    """Requesting an unsupported RDF format raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported export format"):
        _export_rdf(
            sample_graph_data,
            fmt="unsupported",
            namespace_uri="http://example.org/test#",
        )
