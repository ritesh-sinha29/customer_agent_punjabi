import { useState, useCallback } from "react";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  reasoning?: string;
  duration?: number;
}

export interface PendingApproval {
  action: "booking" | "query";
  details: any;
  response: string;
}

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export function useAgentSSE(threadId: string, userId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [pendingApproval, setPendingApproval] =
    useState<PendingApproval | null>(null);

  const startStream = useCallback(
    async (body: any) => {
      setIsLoading(true);
      setPendingApproval(null);
      const startTime = Date.now();

      const assistantMessageId = Date.now().toString() + "-ai";
      let duration: number | undefined = undefined;
      let durationRecorded = false;

      // Add initial empty assistant message to stream tokens into instantly
      setMessages((prev) => [
        ...prev,
        {
          id: assistantMessageId,
          role: "assistant",
          content: "",
          timestamp: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
        },
      ]);

      try {
        const response = await fetch(
          `${BACKEND_URL}/api/v1/agent/chat/stream`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(body),
          },
        );

        if (!response.ok) {
          throw new Error(`Failed to initiate stream: ${response.statusText}`);
        }

        if (!response.body) {
          throw new Error("No response body to stream");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        let accumulatedText = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            const cleanLine = line.trim();
            if (!cleanLine.startsWith("data:")) continue;

            const jsonStr = cleanLine.substring(5).trim();
            if (!jsonStr) continue;

            try {
              const data = JSON.parse(jsonStr);

              if (data.type === "token") {
                accumulatedText += data.content;
                if (!durationRecorded) {
                  duration = (Date.now() - startTime) / 1000;
                  durationRecorded = true;
                }
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, content: accumulatedText, duration }
                      : msg,
                  ),
                );
              } else if (data.type === "reasoning") {
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, reasoning: data.content }
                      : msg,
                  ),
                );
              } else if (data.type === "pending_approval") {
                if (!durationRecorded) {
                  duration = (Date.now() - startTime) / 1000;
                  durationRecorded = true;
                }
                setPendingApproval({
                  action: data.pending_action,
                  details: data.details,
                  response: data.response,
                });
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, content: data.response, duration }
                      : msg,
                  ),
                );
              } else if (data.type === "completed") {
                if (!durationRecorded) {
                  duration = (Date.now() - startTime) / 1000;
                  durationRecorded = true;
                }
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, content: data.response, duration }
                      : msg,
                  ),
                );
              } else if (data.type === "error") {
                if (!durationRecorded) {
                  duration = (Date.now() - startTime) / 1000;
                  durationRecorded = true;
                }
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, content: `Error: ${data.error}`, duration }
                      : msg,
                  ),
                );
              }
            } catch (e) {
              console.error("Failed to parse SSE chunk:", e);
            }
          }
        }
      } catch (err: any) {
        console.error("Error in SSE Stream:", err);
        if (!durationRecorded) {
          duration = (Date.now() - startTime) / 1000;
          durationRecorded = true;
        }
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  content: `Failed to connect to agent: ${err.message}`,
                  duration,
                }
              : msg,
          ),
        );
      } finally {
        setIsLoading(false);
      }
    },
    [threadId, userId],
  );

  const sendMessage = useCallback(
    (message: string) => {
      if (!message.trim()) return;

      const userMsg: Message = {
        id: Date.now().toString() + "-user",
        role: "user",
        content: message,
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      };

      setMessages((prev) => [...prev, userMsg]);
      startStream({
        message,
        thread_id: threadId,
        user_id: userId,
      });
    },
    [threadId, userId, startStream],
  );

  const sendApproval = useCallback(
    (approved: boolean) => {
      const confirmText = approved ? "Yes, confirm." : "No, cancel.";
      const userMsg: Message = {
        id: Date.now().toString() + "-user",
        role: "user",
        content: confirmText,
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      };

      setMessages((prev) => [...prev, userMsg]);
      startStream({
        message: confirmText,
        thread_id: threadId,
        user_id: userId,
        approve: approved,
      });
    },
    [threadId, userId, startStream],
  );

  return {
    messages,
    setMessages,
    isLoading,
    pendingApproval,
    setPendingApproval,
    sendMessage,
    sendApproval,
  };
}
