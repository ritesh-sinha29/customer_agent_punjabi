import { useState, useCallback, useRef, useEffect } from "react";
import { toast } from "sonner";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  reasoning?: string;
  duration?: number;
  approvalCard?: PendingApproval;
  memoryUpdated?: boolean;
}

export interface PendingApproval {
  action: "booking" | "query";
  details: any;
  response: string;
  status?: "pending" | "approved" | "rejected";
}

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export function useAgentSSE(threadId: string, userId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [pendingApproval, setPendingApproval] =
    useState<PendingApproval | null>(null);
  const lastSeenSummaryRef = useRef<string>("");

  // Initialize the ref with the user's existing latest memory summary on load
  useEffect(() => {
    if (!userId) return;
    const initializeMemoryRef = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/api/v1/agent/memory?user_id=${userId}`);
        if (res.ok) {
          const memData = await res.json();
          const summaries = memData.episodic_summaries || [];
          lastSeenSummaryRef.current = summaries[summaries.length - 1] || "";
        }
      } catch (err) {
        console.error("Failed to initialize memory ref on load:", err);
      }
    };
    initializeMemoryRef();
  }, [userId]);

  const startStream = useCallback(
    async (body: any) => {
      setIsLoading(true);
      setPendingApproval(null);
      const startTime = Date.now();
      let reasoningStartTime: number | null = null;
      let toastFired = false;

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
                  duration =
                    (Date.now() - (reasoningStartTime || startTime)) / 1000;
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
                if (!reasoningStartTime) {
                  reasoningStartTime = Date.now();
                }
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, reasoning: data.content }
                      : msg,
                  ),
                );
              } else if (data.type === "pending_approval") {
                if (!durationRecorded) {
                  duration =
                    (Date.now() - (reasoningStartTime || startTime)) / 1000;
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
              } else if (data.type === "tool_success") {
                if (!toastFired) {
                  toast.success(
                    data.tool === "create_booking"
                      ? "Your products have been booked! You will get notified by our company soon."
                      : "Your support request has been submitted successfully!",
                    { duration: 5000 },
                  );
                  toastFired = true;
                }
              } else if (data.type === "completed") {
                if (!durationRecorded) {
                  duration =
                    (Date.now() - (reasoningStartTime || startTime)) / 1000;
                  durationRecorded = true;
                }
                if (body?.approve === true && !toastFired) {
                  toast.success(
                    "Your products have been booked! You will get notified by our company soon.",
                    { duration: 5000 },
                  );
                  toastFired = true;
                }
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, content: data.response, duration }
                      : msg,
                  ),
                );

                // Poll memory endpoint every 2 seconds (up to 6 times) to capture background update
                let pollAttempts = 0;
                const intervalId = setInterval(async () => {
                  pollAttempts++;
                  try {
                    const res = await fetch(
                      `${BACKEND_URL}/api/v1/agent/memory?user_id=${userId}`,
                    );
                    if (res.ok) {
                      const memData = await res.json();
                      const summaries = memData.episodic_summaries || [];
                      const latestSummary = summaries[summaries.length - 1] || "";

                      if (
                        latestSummary &&
                        latestSummary !== lastSeenSummaryRef.current
                      ) {
                        lastSeenSummaryRef.current = latestSummary;
                        clearInterval(intervalId);
                        toast.success("Your new memory is updated.", {
                          duration: 5000,
                        });
                        setMessages((prev) =>
                          prev.map((msg) =>
                            msg.id === assistantMessageId
                              ? { ...msg, memoryUpdated: true }
                              : msg,
                          ),
                        );
                      }
                    }
                  } catch (err) {
                    console.error("Error verifying memory update:", err);
                  }

                  if (pollAttempts >= 6) {
                    clearInterval(intervalId);
                  }
                }, 2000);
              } else if (data.type === "error") {
                if (!durationRecorded) {
                  duration =
                    (Date.now() - (reasoningStartTime || startTime)) / 1000;
                  durationRecorded = true;
                }
                if (body?.approve === true) {
                  toast.error(`Failed to process action: ${data.error}`);
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
          duration = (Date.now() - (reasoningStartTime || startTime)) / 1000;
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
        if (typeof window !== "undefined") {
          window.dispatchEvent(new Event("threads-updated"));
        }
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

      const cardToPreserve: PendingApproval | undefined = pendingApproval
        ? {
            ...pendingApproval,
            status: approved ? "approved" : "rejected",
          }
        : undefined;

      if (!approved) {
        toast.info("Action cancelled.", { duration: 3000 });
      }

      const userMsg: Message = {
        id: Date.now().toString() + "-user",
        role: "user",
        content: confirmText,
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
        approvalCard: cardToPreserve,
      };

      setMessages((prev) => [...prev, userMsg]);
      startStream({
        message: confirmText,
        thread_id: threadId,
        user_id: userId,
        approve: approved,
      });
    },
    [threadId, userId, startStream, pendingApproval],
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
