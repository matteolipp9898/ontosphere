import { TaskStatus } from "@/types/ontology";
import { Card, CardContent } from "@/components/ui/card";
import { Loader2 } from "lucide-react";

interface ProcessingOverlayProps {
  status: TaskStatus | null;
  isProcessing: boolean;
}

export default function ProcessingOverlay({ status, isProcessing }: ProcessingOverlayProps) {
  if (!isProcessing) return null;

  const progress = status?.progress ?? 0;
  const message = status?.message ?? "Processing documents...";

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-background/60 backdrop-blur-sm">
      <Card className="w-80 shadow-xl">
        <CardContent className="flex flex-col items-center p-8">
          <Loader2 className="h-10 w-10 animate-spin text-primary" />
          <p className="mt-4 text-center font-medium">{message}</p>

          {progress > 0 && (
            <div className="mt-4 w-full">
              <div className="flex items-center justify-between text-sm text-muted-foreground">
                <span>Progress</span>
                <span>{Math.round(progress)}%</span>
              </div>
              <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-500"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}

          {status?.status && (
            <p className="mt-3 text-xs text-muted-foreground">Stage: {status.status}</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
