import { useEffect, useRef, useState, useCallback } from "react";

interface WebSocketMessage {
  type: string;
  payload: Record<string, unknown>;
  [key: string]: unknown;
}

interface UseWebSocketReturn {
  lastMessage: WebSocketMessage | null;
  isConnected: boolean;
}

export function useWebSocket(ontologyId: string | undefined): UseWebSocketReturn {
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    if (!ontologyId) return;

    const wsBase =
      import.meta.env.VITE_WS_BASE_URL ??
      `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`;

    const wsUrl = `${wsBase}/api/ontologies/${ontologyId}/events`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.addEventListener("open", () => {
      setIsConnected(true);
    });

    ws.addEventListener("message", (event: MessageEvent) => {
      try {
        const parsed = JSON.parse(event.data as string) as WebSocketMessage;
        setLastMessage(parsed);
      } catch {
        console.warn("[WebSocket] Failed to parse message:", event.data);
      }
    });

    ws.addEventListener("close", () => {
      setIsConnected(false);
      wsRef.current = null;

      // Attempt reconnect after 3 seconds
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, 3000);
    });

    ws.addEventListener("error", () => {
      ws.close();
    });
  }, [ontologyId]);

  useEffect(() => {
    connect();

    return () => {
      clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  return { lastMessage, isConnected };
}
