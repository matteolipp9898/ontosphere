import { useState, useEffect, useMemo } from "react";
import { GraphNode, GraphEdge } from "@/types/ontology";
import {
  useUpdateClass,
  useDeleteClass,
  useAddClass,
  useAddRelationship,
  useGraph,
} from "@/api/ontologies";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Save, Trash2, Plus, ChevronRight, Network } from "lucide-react";
import { toast } from "sonner";

interface NodePanelProps {
  node: GraphNode | null;
  ontologyId: string;
  editMode: boolean;
  edges: GraphEdge[];
}

const TYPE_COLORS: Record<string, string> = {
  class: "bg-blue-100 text-blue-800",
  property: "bg-green-100 text-green-800",
  individual: "bg-purple-100 text-purple-800",
};

const RELATIONSHIP_TYPES = [
  "SUBCLASS_OF",
  "HAS_PROPERTY",
  "DOMAIN",
  "RANGE",
  "RELATED_TO",
  "EQUIVALENT_TO",
  "DISJOINT_WITH",
];

export default function NodePanel({ node, ontologyId, editMode, edges }: NodePanelProps) {
  const updateClass = useUpdateClass(ontologyId);
  const deleteClass = useDeleteClass(ontologyId);
  const addClass = useAddClass(ontologyId);
  const addRelationship = useAddRelationship(ontologyId);
  const { data: graphData } = useGraph(ontologyId);

  // Edit state for selected node
  const [editLabel, setEditLabel] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  // Add class form state
  const [newClassUri, setNewClassUri] = useState("");
  const [newClassLabel, setNewClassLabel] = useState("");
  const [newClassDescription, setNewClassDescription] = useState("");
  const [newClassParent, setNewClassParent] = useState("");

  // Add relationship form state
  const [relTarget, setRelTarget] = useState("");
  const [relType, setRelType] = useState("");

  // Reset edit state when node changes
  useEffect(() => {
    if (node) {
      setEditLabel(node.label || "");
      setEditDescription(node.description || "");
    }
  }, [node]);

  // Compute connected edges
  const connectedEdges = useMemo(() => {
    if (!node) return { incoming: [], outgoing: [] };

    const incoming = edges.filter((e) => e.target === node.id);
    const outgoing = edges.filter((e) => e.source === node.id);
    return { incoming, outgoing };
  }, [node, edges]);

  // Get all class nodes for dropdowns
  const classNodes = useMemo(() => {
    return (graphData?.nodes ?? []).filter((n) => n.node_type === "class");
  }, [graphData]);

  // All nodes for relationship target dropdown
  const allNodes = useMemo(() => {
    return graphData?.nodes ?? [];
  }, [graphData]);

  const handleSaveChanges = async () => {
    if (!node) return;
    try {
      await updateClass.mutateAsync({
        uri: node.uri,
        payload: {
          label: editLabel.trim(),
          description: editDescription.trim() || undefined,
        },
      });
      toast.success("Node updated");
    } catch {
      toast.error("Failed to update node");
    }
  };

  const handleDelete = async () => {
    if (!node) return;
    try {
      await deleteClass.mutateAsync(node.uri);
      toast.success("Node deleted");
      setDeleteDialogOpen(false);
    } catch {
      toast.error("Failed to delete node");
    }
  };

  const handleAddClass = async () => {
    if (!newClassUri.trim() || !newClassLabel.trim()) {
      toast.error("URI and Label are required");
      return;
    }
    try {
      await addClass.mutateAsync({
        uri: newClassUri.trim(),
        label: newClassLabel.trim(),
        description: newClassDescription.trim() || undefined,
        parent_uri: newClassParent || undefined,
      });
      toast.success("Class added");
      setNewClassUri("");
      setNewClassLabel("");
      setNewClassDescription("");
      setNewClassParent("");
    } catch {
      toast.error("Failed to add class");
    }
  };

  const handleAddRelationship = async () => {
    if (!node || !relTarget || !relType) {
      toast.error("Select a target node and relationship type");
      return;
    }
    try {
      await addRelationship.mutateAsync({
        source_uri: node.uri,
        target_uri: relTarget,
        relationship_type: relType,
      });
      toast.success("Relationship added");
      setRelTarget("");
      setRelType("");
    } catch {
      toast.error("Failed to add relationship");
    }
  };

  if (!node) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6 text-muted-foreground">
        <Network className="h-10 w-10 opacity-30" />
        <p className="mt-3 text-sm">Select a node to view details</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <Tabs defaultValue="details" className="flex flex-1 flex-col overflow-hidden">
        <TabsList className="mx-4 mt-4 shrink-0">
          <TabsTrigger value="details">Details</TabsTrigger>
          {editMode && <TabsTrigger value="add">Add</TabsTrigger>}
        </TabsList>

        {/* Details Tab */}
        <TabsContent value="details" className="flex-1 overflow-y-auto px-4 pb-4">
          <div className="space-y-4">
            {/* Type Badge */}
            <div className="flex items-center gap-2">
              <Badge
                variant="secondary"
                className={TYPE_COLORS[node.node_type] ?? TYPE_COLORS.class}
              >
                {node.node_type}
              </Badge>
            </div>

            {/* URI */}
            <div>
              <Label className="text-xs text-muted-foreground">URI</Label>
              <p className="mt-0.5 break-all font-mono text-xs">{node.uri}</p>
            </div>

            {/* Label */}
            <div>
              <Label htmlFor="nodeLabel">Label</Label>
              {editMode ? (
                <Input
                  id="nodeLabel"
                  value={editLabel}
                  onChange={(e) => setEditLabel(e.target.value)}
                  className="mt-1"
                />
              ) : (
                <p className="mt-0.5 text-sm font-medium">{node.label}</p>
              )}
            </div>

            {/* Description */}
            <div>
              <Label htmlFor="nodeDesc">Description</Label>
              {editMode ? (
                <Textarea
                  id="nodeDesc"
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  rows={3}
                  className="mt-1"
                />
              ) : (
                <p className="mt-0.5 text-sm text-muted-foreground">
                  {node.description || "No description"}
                </p>
              )}
            </div>

            {/* Edit Actions */}
            {editMode && (
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={handleSaveChanges}
                  disabled={updateClass.isPending}
                >
                  <Save className="mr-1.5 h-3.5 w-3.5" />
                  Save Changes
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => setDeleteDialogOpen(true)}
                >
                  <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                  Delete
                </Button>
              </div>
            )}

            {/* Connected Edges */}
            <div>
              <h4 className="mb-2 text-sm font-medium">
                Connections ({connectedEdges.outgoing.length + connectedEdges.incoming.length})
              </h4>

              {connectedEdges.outgoing.length > 0 && (
                <div className="mb-2">
                  <p className="mb-1 text-xs font-medium text-muted-foreground">Outgoing</p>
                  <ul className="space-y-1">
                    {connectedEdges.outgoing.map((edge, i) => (
                      <li
                        key={`out-${i}`}
                        className="flex items-center gap-1.5 text-xs"
                      >
                        <ChevronRight className="h-3 w-3 text-muted-foreground" />
                        <Badge variant="outline" className="text-[10px]">
                          {edge.edge_type}
                        </Badge>
                        <span className="truncate">{edge.target}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {connectedEdges.incoming.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-medium text-muted-foreground">Incoming</p>
                  <ul className="space-y-1">
                    {connectedEdges.incoming.map((edge, i) => (
                      <li
                        key={`in-${i}`}
                        className="flex items-center gap-1.5 text-xs"
                      >
                        <ChevronRight className="h-3 w-3 rotate-180 text-muted-foreground" />
                        <Badge variant="outline" className="text-[10px]">
                          {edge.edge_type}
                        </Badge>
                        <span className="truncate">{edge.source}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {connectedEdges.outgoing.length === 0 && connectedEdges.incoming.length === 0 && (
                <p className="text-xs text-muted-foreground">No connections</p>
              )}
            </div>
          </div>
        </TabsContent>

        {/* Add Tab (edit mode only) */}
        {editMode && (
          <TabsContent value="add" className="flex-1 overflow-y-auto px-4 pb-4">
            <div className="space-y-6">
              {/* Add Class Form */}
              <div className="rounded-lg border p-4">
                <h4 className="mb-3 flex items-center gap-1.5 text-sm font-medium">
                  <Plus className="h-3.5 w-3.5" />
                  Add Class
                </h4>
                <div className="space-y-3">
                  <div>
                    <Label htmlFor="addClass-uri" className="text-xs">
                      URI <span className="text-destructive">*</span>
                    </Label>
                    <Input
                      id="addClass-uri"
                      placeholder="e.g., http://example.org/MyClass"
                      value={newClassUri}
                      onChange={(e) => setNewClassUri(e.target.value)}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label htmlFor="addClass-label" className="text-xs">
                      Label <span className="text-destructive">*</span>
                    </Label>
                    <Input
                      id="addClass-label"
                      placeholder="My Class"
                      value={newClassLabel}
                      onChange={(e) => setNewClassLabel(e.target.value)}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label htmlFor="addClass-desc" className="text-xs">
                      Description
                    </Label>
                    <Textarea
                      id="addClass-desc"
                      placeholder="Optional description..."
                      value={newClassDescription}
                      onChange={(e) => setNewClassDescription(e.target.value)}
                      rows={2}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label htmlFor="addClass-parent" className="text-xs">
                      Parent Class
                    </Label>
                    <Select value={newClassParent} onValueChange={setNewClassParent}>
                      <SelectTrigger className="mt-1">
                        <SelectValue placeholder="None (top-level)" />
                      </SelectTrigger>
                      <SelectContent>
                        {classNodes.map((cn) => (
                          <SelectItem key={cn.id} value={cn.uri}>
                            {cn.label || cn.id}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <Button
                    size="sm"
                    onClick={handleAddClass}
                    disabled={addClass.isPending}
                    className="w-full"
                  >
                    <Plus className="mr-1.5 h-3.5 w-3.5" />
                    Add Class
                  </Button>
                </div>
              </div>

              {/* Add Relationship Form */}
              <div className="rounded-lg border p-4">
                <h4 className="mb-3 flex items-center gap-1.5 text-sm font-medium">
                  <Plus className="h-3.5 w-3.5" />
                  Add Relationship
                </h4>
                <div className="space-y-3">
                  <div>
                    <Label className="text-xs">From</Label>
                    <p className="mt-0.5 truncate text-sm font-medium">
                      {node.label || node.id}
                    </p>
                  </div>
                  <div>
                    <Label htmlFor="rel-target" className="text-xs">
                      Target Node
                    </Label>
                    <Select value={relTarget} onValueChange={setRelTarget}>
                      <SelectTrigger className="mt-1">
                        <SelectValue placeholder="Select target..." />
                      </SelectTrigger>
                      <SelectContent>
                        {allNodes
                          .filter((n) => n.id !== node.id)
                          .map((n) => (
                            <SelectItem key={n.id} value={n.uri}>
                              {n.label || n.uri}
                            </SelectItem>
                          ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="rel-type" className="text-xs">
                      Relationship Type
                    </Label>
                    <Select value={relType} onValueChange={setRelType}>
                      <SelectTrigger className="mt-1">
                        <SelectValue placeholder="Select type..." />
                      </SelectTrigger>
                      <SelectContent>
                        {RELATIONSHIP_TYPES.map((type) => (
                          <SelectItem key={type} value={type}>
                            {type.replace(/_/g, " ")}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <Button
                    size="sm"
                    onClick={handleAddRelationship}
                    disabled={addRelationship.isPending || !relTarget || !relType}
                    className="w-full"
                  >
                    <Plus className="mr-1.5 h-3.5 w-3.5" />
                    Add Relationship
                  </Button>
                </div>
              </div>
            </div>
          </TabsContent>
        )}
      </Tabs>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Node</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete "{node.label || node.id}"? This will also remove
              all connected relationships. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteClass.isPending}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
