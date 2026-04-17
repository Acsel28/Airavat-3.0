/**
 * useStreamingResponse - Hook to handle streaming response from /loan/chat-stream endpoint
 * Parses Server-Sent Events and provides callback handlers for chunks and metadata
 */

import { useRef, useCallback } from "react";

export function useStreamingResponse() {
  const abortControllerRef = useRef(null);

  const fetchStream = useCallback(async (payload, onChunk, onMetadata, onError) => {
    try {
      abortControllerRef.current = new AbortController();

      const res = await fetch("/loan/chat-stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: abortControllerRef.current.signal,
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");

        // Process complete lines
        for (let i = 0; i < lines.length - 1; i++) {
          const line = lines[i].trim();
          if (line.startsWith("data: ")) {
            try {
              const jsonStr = line.substring(6);
              const event = JSON.parse(jsonStr);

              if (event.type === "text" && onChunk) {
                onChunk(event.chunk || "");
              } else if (event.type === "metadata" && onMetadata) {
                onMetadata(event);
              } else if (event.type === "error" && onError) {
                onError(event.message || "Unknown error");
              } else if (event.type === "done") {
                break;
              }
            } catch (e) {
              console.error("Error parsing SSE event:", e);
            }
          }
        }

        // Keep unparsed partial line in buffer
        buffer = lines[lines.length - 1];
      }
    } catch (err) {
      if (err.name !== "AbortError") {
        if (onError) {
          onError(err.message || "Failed to stream response");
        }
      }
    }
  }, []);

  const cancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  }, []);

  return { fetchStream, cancel };
}
