import { useEffect, useRef, useState, useCallback } from "react";

export type ConnectionState = "connecting" | "connected" | "disconnected" | "dormant";

interface WebSocketMessage {
  type: string;
  payload: Record<string, unknown>;
  [key: string]: unknown;
}

interface UseWebSocketReturn {
  lastMessage: WebSocketMessage | null;
  connectionState: ConnectionState;
  /** @deprecated Use connectionState === "connected" instead */
  isConnected: boolean;
  /** Force an immediate reconnection attempt (resets backoff). */
  reconnectNow: () => void;
}

/** Max retries before switching from active backoff to dormant mode. */
const MAX_ACTIVE_RETRIES = 5;
/** Initial backoff delay in ms. */
const INITIAL_BACKOFF_MS = 1_000;
/** Maximum backoff delay during active retries. */
const MAX_BACKOFF_MS = 30_000;
/** Retry interval once in dormant mode. */
const DORMANT_INTERVAL_MS = 60_000;

export function useWebSocket(ontologyId: string | undefined): UseWebSocketReturn {
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>("disconnected");

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const retriesRef = useRef(0);
  const backoffRef = useRef(INITIAL_BACKOFF_MS);
  const unmountedRef = useRef(false);

  const resetBackoff = useCallback(() => {
    retriesRef.current = 0;
    backoffRef.current = INITIAL_BACKOFF_MS;
  }, []);

  const scheduleReconnect = useCallback(
    (connectFn: () => void) => {
      if (unmountedRef.current) return;

      retriesRef.current += 1;

      if (retriesRef.current > MAX_ACTIVE_RETRIES) {
        // Switch to dormant mode — slow retries at a fixed interval
        setConnectionState("dormant");
        reconnectTimeoutRef.current = setTimeout(connectFn, DORMANT_INTERVAL_MS);
      } else {
        // Active backoff: 1s → 2s → 4s → 8s → 16s → 30s (cap)
        setConnectionState("disconnected");
        reconnectTimeoutRef.current = setTimeout(connectFn, backoffRef.current);
        backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
      }
    },
    [],
  );

  const connect = useCallback(() => {
    if (!ontologyId || unmountedRef.current) return;

    // Clean up any existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setConnectionState("connecting");

    const wsBase =
      import.meta.env.VITE_WS_BASE_URL ??
      `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`;

    const wsUrl = `${wsBase}/api/ontologies/${ontologyId}/events`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.addEventListener("open", () => {
      if (unmountedRef.current) return;
      setConnectionState("connected");
      resetBackoff();
    });

    ws.addEventListener("message", (event: MessageEvent) => {
      if (unmountedRef.current) return;
      try {
        const parsed = JSON.parse(event.data as string) as WebSocketMessage;
        // Ignore server heartbeat pings
        if (parsed.type === "ping") return;
        setLastMessage(parsed);
      } catch {
        console.warn("[WebSocket] Failed to parse message:", event.data);
      }
    });

    ws.addEventListener("close", () => {
      if (unmountedRef.current) return;
      wsRef.current = null;
      scheduleReconnect(connect);
    });

    ws.addEventListener("error", () => {
      // The close event will fire after error, which triggers reconnect
      ws.close();
    });
  }, [ontologyId, resetBackoff, scheduleReconnect]);

  const reconnectNow = useCallback(() => {
    clearTimeout(reconnectTimeoutRef.current);
    resetBackoff();
    connect();
  }, [connect, resetBackoff]);

  useEffect(() => {
    unmountedRef.current = false;
    connect();

    return () => {
      unmountedRef.current = true;
      clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  return {
    lastMessage,
    connectionState,
    isConnected: connectionState === "connected",
    reconnectNow,
  };
}
