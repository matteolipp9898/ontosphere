import { useCallback, useEffect, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  useOntology,
  useGraph,
  useValidateOntology,
  downloadExport,
  useCreateVersion,
  useOntologyStatus,
} from "@/api/ontologies";
import { useOntologyStore } from "@/store/ontologyStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import type { GraphNode } from "@/types/ontology";
import Toolbar from "@/components/Toolbar";
import GraphViewer from "@/components/GraphViewer";
import NodePanel from "@/components/NodePanel";
import ProcessingOverlay from "@/components/ProcessingOverlay";
import ValidationPanel from "@/components/ValidationPanel";
import { Button } from "@/components/ui/button";
import { Loader2, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

export default function OntologyEditor() {
  const { id: ontologyId } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const {
    selectedNodeId,
    editMode,
    searchQuery,
    sidePanel,
    validationResult,
    setSelectedNode,
    toggleEditMode,
    setSearchQuery,
    setSidePanel,
    setValidationResult,
  } = useOntologyStore();

  const {
    data: ontology,
    isLoading: ontologyLoading,
    error: ontologyError,
  } = useOntology(ontologyId!);
  const { data: graphData, isLoading: graphLoading } = useGraph(ontologyId!);

  const isProcessing = ontology?.status === "processing";
  const { data: taskStatus } = useOntologyStatus(ontologyId!, isProcessing);

  const validateOntology = useValidateOntology(ontologyId!);
  const createVersion = useCreateVersion(ontologyId!);

  // WebSocket for live updates during processing
  const { lastMessage, isConnected } = useWebSocket(ontologyId!);

  // Handle WebSocket messages for status updates
  useEffect(() => {
    if (!lastMessage) return;
    if (lastMessage.type === "status_update") {
      const status = lastMessage.payload?.status as string | undefined;
      if (status === "ready") {
        toast.success("Ontology processing complete!");
      }
      if (status === "error") {
        const msg = (lastMessage.payload?.message as string) ?? "Unknown error";
        toast.error(`Processing failed: ${msg}`);
      }
    }
  }, [lastMessage]);

  // Find the selected node from graph data
  const selectedNode: GraphNode | null = useMemo(() => {
    if (!selectedNodeId || !graphData?.nodes) return null;
    return graphData.nodes.find((n) => n.id === selectedNodeId) ?? null;
  }, [selectedNodeId, graphData]);

  const edges = useMemo(() => graphData?.edges ?? [], [graphData]);

  // Callbacks
  const handleNodeSelect = useCallback(
    (nodeId: string | null) => {
      setSelectedNode(nodeId);
      if (nodeId) {
        setSidePanel("details");
      }
    },
    [setSelectedNode, setSidePanel],
  );

  const handleToggleEditMode = useCallback(() => {
    toggleEditMode();
  }, [toggleEditMode]);

  const handleSearchChange = useCallback(
    (q: string) => {
      setSearchQuery(q);
    },
    [setSearchQuery],
  );

  const handleValidate = useCallback(async () => {
    try {
      const result = await validateOntology.mutateAsync();
      setValidationResult(result);
      setSidePanel("validation");
      if (result.conforms) {
        toast.success("Validation passed - no issues found");
      } else {
        toast.warning(`Validation found ${result.violations?.length ?? 0} issue(s)`);
      }
    } catch {
      toast.error("Validation failed");
    }
  }, [validateOntology, setValidationResult, setSidePanel]);

  const handleExport = useCallback(
    async (format: string) => {
      try {
        await downloadExport(ontologyId!, format, ontology?.name);
        toast.success(`Exported as ${format.toUpperCase()}`);
      } catch {
        toast.error("Export failed");
      }
    },
    [ontologyId, ontology?.name],
  );

  const handleCreateVersion = useCallback(async () => {
    try {
      await createVersion.mutateAsync("Version created from editor");
      toast.success("Version created");
    } catch {
      toast.error("Failed to create version");
    }
  }, [createVersion]);

  // Loading state
  if (ontologyLoading || graphLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="flex flex-col items-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="mt-3 text-sm text-muted-foreground">Loading ontology...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (ontologyError || !ontology) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="flex flex-col items-center">
          <AlertTriangle className="h-8 w-8 text-destructive" />
          <p className="mt-3 text-sm text-destructive">Failed to load ontology</p>
          <Button variant="outline" className="mt-4" onClick={() => navigate("/")}>
            Back to Dashboard
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {/* Toolbar */}
      <Toolbar
        ontology={ontology}
        onValidate={handleValidate}
        onExport={handleExport}
        onCreateVersion={handleCreateVersion}
        onToggleEditMode={handleToggleEditMode}
        editMode={editMode}
        searchQuery={searchQuery}
        onSearchChange={handleSearchChange}
      />

      {/* Main Content Area */}
      <div className="relative flex flex-1 overflow-hidden">
        {/* Graph Viewer (center) */}
        <div className="relative flex-1 overflow-hidden">
          <GraphViewer
            data={graphData ?? { nodes: [], edges: [] }}
            onNodeSelect={handleNodeSelect}
            searchQuery={searchQuery}
            editMode={editMode}
            selectedNodeId={selectedNodeId}
          />

          {/* Processing Overlay */}
          <ProcessingOverlay
            status={taskStatus ?? null}
            isProcessing={isProcessing}
          />

          {/* Validation Panel (floating at bottom of graph) */}
          {validationResult && (
            <div className="absolute bottom-4 left-4 right-4 z-40 max-w-xl">
              <div className="relative">
                <button
                  className="absolute right-2 top-2 z-10 text-xs text-muted-foreground hover:text-foreground"
                  onClick={() => setValidationResult(null)}
                >
                  Dismiss
                </button>
                <ValidationPanel result={validationResult} />
              </div>
            </div>
          )}
        </div>

        {/* Side Panel (right) */}
        <div
          className={cn(
            "shrink-0 border-l bg-white transition-all duration-200",
            sidePanel !== null ? "w-[350px]" : "w-0",
          )}
        >
          {sidePanel !== null && (
            <div className="flex h-full flex-col">
              <div className="flex items-center justify-between border-b px-4 py-2">
                <h2 className="text-sm font-medium">Node Details</h2>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setSidePanel(null);
                    setSelectedNode(null);
                  }}
                  className="h-7 w-7 p-0"
                >
                  &times;
                </Button>
              </div>
              <div className="flex-1 overflow-hidden">
                <NodePanel
                  node={selectedNode}
                  ontologyId={ontologyId!}
                  editMode={editMode}
                  edges={edges}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
