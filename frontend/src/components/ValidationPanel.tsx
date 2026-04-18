import { ValidationResult } from "@/types/ontology";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { CheckCircle, XCircle, AlertTriangle } from "lucide-react";

interface ValidationPanelProps {
  result: ValidationResult | null;
}

function SeverityIcon({ severity }: { severity: string }) {
  switch (severity) {
    case "error":
      return <XCircle className="h-4 w-4 shrink-0 text-red-500" />;
    case "warning":
      return <AlertTriangle className="h-4 w-4 shrink-0 text-yellow-500" />;
    default:
      return <AlertTriangle className="h-4 w-4 shrink-0 text-blue-500" />;
  }
}

export default function ValidationPanel({ result }: ValidationPanelProps) {
  if (!result) return null;

  const conforms = result.conforms;
  const violations = result.violations ?? [];

  return (
    <Card className="mt-4">
      <CardHeader className={conforms ? "bg-green-50" : "bg-red-50"}>
        <CardTitle className="flex items-center gap-2 text-base">
          {conforms ? (
            <>
              <CheckCircle className="h-5 w-5 text-green-600" />
              <span className="text-green-800">Validation Passed</span>
            </>
          ) : (
            <>
              <XCircle className="h-5 w-5 text-red-600" />
              <span className="text-red-800">
                Validation Failed ({violations.length} issue{violations.length !== 1 ? "s" : ""})
              </span>
            </>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {conforms ? (
          <div className="flex items-center justify-center py-6 text-sm text-muted-foreground">
            <CheckCircle className="mr-2 h-4 w-4 text-green-500" />
            No issues found. The ontology is valid.
          </div>
        ) : (
          <ul className="divide-y">
            {violations.map((violation, index) => (
              <li key={index} className="flex gap-3 px-4 py-3">
                <SeverityIcon severity={violation.severity ?? "error"} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{violation.message}</p>
                  {violation.focus_node && (
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">
                      Node: {violation.focus_node}
                    </p>
                  )}
                  {violation.path && (
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">
                      Path: {violation.path}
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
