import { useNavigate } from "react-router-dom";
import { useOntologies } from "@/api/ontologies";
import { Ontology } from "@/types/ontology";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Brain, Plus, Loader2, FileText, Network } from "lucide-react";

const STATUS_STYLES: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; className: string }> = {
  draft: { variant: "secondary", className: "bg-gray-100 text-gray-700 hover:bg-gray-100" },
  processing: { variant: "secondary", className: "bg-yellow-100 text-yellow-800 hover:bg-yellow-100" },
  ready: { variant: "secondary", className: "bg-green-100 text-green-800 hover:bg-green-100" },
  error: { variant: "destructive", className: "" },
};

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.draft;
  return (
    <Badge variant={style.variant} className={style.className}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </Badge>
  );
}

function OntologyCard({ ontology, onClick }: { ontology: Ontology; onClick: () => void }) {
  return (
    <Card
      className="cursor-pointer transition-shadow hover:shadow-lg"
      onClick={onClick}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <CardTitle className="text-lg leading-tight">{ontology.name}</CardTitle>
          <StatusBadge status={ontology.status} />
        </div>
        {ontology.description && (
          <CardDescription className="line-clamp-2 mt-1">
            {ontology.description}
          </CardDescription>
        )}
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <span className="flex items-center gap-1">
            <FileText className="h-3.5 w-3.5" />
            {ontology.document_count ?? 0} docs
          </span>
          <span className="flex items-center gap-1">
            <Network className="h-3.5 w-3.5" />
            {ontology.status}
          </span>
        </div>
        <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
          <span>Created {formatDate(ontology.created_at)}</span>
          <span>Updated {formatDate(ontology.updated_at)}</span>
        </div>
      </CardContent>
    </Card>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const { data: ontologies, isLoading, error } = useOntologies();

  const stats = {
    total: ontologies?.length ?? 0,
    processing: ontologies?.filter((o) => o.status === "processing").length ?? 0,
    ready: ontologies?.filter((o) => o.status === "ready").length ?? 0,
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-6">
          <div className="flex items-center gap-3">
            <Brain className="h-8 w-8 text-primary" />
            <div>
              <h1 className="text-2xl font-bold tracking-tight">OntoSphere</h1>
              <p className="text-sm text-muted-foreground">
                From documents to knowledge — automatically.
              </p>
            </div>
          </div>
          <Button onClick={() => navigate("/ontologies/new")}>
            <Plus className="mr-2 h-4 w-4" />
            New Ontology
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8">
        {/* Stats Bar */}
        {!isLoading && !error && ontologies && ontologies.length > 0 && (
          <div className="mb-8 grid grid-cols-3 gap-4">
            <Card>
              <CardContent className="flex items-center gap-3 p-4">
                <div className="rounded-lg bg-blue-50 p-2">
                  <Network className="h-5 w-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{stats.total}</p>
                  <p className="text-sm text-muted-foreground">Total Ontologies</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex items-center gap-3 p-4">
                <div className="rounded-lg bg-yellow-50 p-2">
                  <Loader2 className="h-5 w-5 text-yellow-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{stats.processing}</p>
                  <p className="text-sm text-muted-foreground">Processing</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex items-center gap-3 p-4">
                <div className="rounded-lg bg-green-50 p-2">
                  <Brain className="h-5 w-5 text-green-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{stats.ready}</p>
                  <p className="text-sm text-muted-foreground">Ready</p>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Loading State */}
        {isLoading && (
          <div className="flex flex-col items-center justify-center py-24">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            <p className="mt-4 text-muted-foreground">Loading ontologies...</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="flex flex-col items-center justify-center py-24">
            <p className="text-destructive">Failed to load ontologies. Please try again.</p>
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !error && ontologies && ontologies.length === 0 && (
          <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-24">
            <Brain className="h-12 w-12 text-muted-foreground/50" />
            <h2 className="mt-4 text-lg font-semibold">No ontologies yet</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Create your first ontology to get started.
            </p>
            <Button className="mt-6" onClick={() => navigate("/ontologies/new")}>
              <Plus className="mr-2 h-4 w-4" />
              New Ontology
            </Button>
          </div>
        )}

        {/* Ontology Grid */}
        {!isLoading && !error && ontologies && ontologies.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {ontologies.map((ontology) => (
              <OntologyCard
                key={ontology.id}
                ontology={ontology}
                onClick={() => navigate(`/ontologies/${ontology.id}`)}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
