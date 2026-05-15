import type { ConnectionState } from "@/hooks/useWebSocket";
import { WifiOff, RefreshCw } from "lucide-react";

interface ConnectionBannerProps {
  connectionState: ConnectionState;
  onReconnect: () => void;
}

export default function ConnectionBanner({
  connectionState,
  onReconnect,
}: ConnectionBannerProps) {
  if (connectionState === "connected" || connectionState === "connecting") {
    return null;
  }

  const isDormant = connectionState === "dormant";

  return (
    <div className="absolute left-1/2 top-3 z-50 -translate-x-1/2">
      <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs text-amber-800 shadow-sm">
        <WifiOff className="h-3.5 w-3.5 shrink-0" />
        <span>
          {isDormant
            ? "Live updates unavailable"
            : "Reconnecting..."}
        </span>
        {isDormant && (
          <button
            onClick={onReconnect}
            className="ml-1 inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-medium text-amber-900 hover:bg-amber-100"
          >
            <RefreshCw className="h-3 w-3" />
            Retry
          </button>
        )}
      </div>
    </div>
  );
}
