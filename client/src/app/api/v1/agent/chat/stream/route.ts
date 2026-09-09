import { NextRequest } from "next/server";
import { Redis } from "@upstash/redis";
import { Ratelimit } from "@upstash/ratelimit";

// Create Redis instance from environment variables (UPSTASH_REDIS_REST_URL & UPSTASH_REDIS_REST_TOKEN)
const redis = Redis.fromEnv();

// Create 5 requests per minute sliding window rate limiter
const minLimiter = new Ratelimit({
  redis,
  limiter: Ratelimit.slidingWindow(5, "60 s"),
  prefix: "ratelimit:min",
  analytics: true,
});

// Create 100 requests per day (86400s) sliding window rate limiter
const dayLimiter = new Ratelimit({
  redis,
  limiter: Ratelimit.slidingWindow(100, "86400 s"),
  prefix: "ratelimit:day",
  analytics: true,
});

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const userId = body?.user_id || "anonymous";

    // Perform rate limit checks with 1s timeout safeguard so network latency to Upstash never hangs the user query
    let minResult = { success: true, limit: 5, remaining: 5 };
    let dayResult = { success: true, limit: 100, remaining: 100 };

    try {
      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error("Rate limit check timeout")), 1000)
      );

      const limitPromise = Promise.all([
        minLimiter.limit(userId),
        dayLimiter.limit(userId),
      ]);

      const [mRes, dRes] = (await Promise.race([
        limitPromise,
        timeoutPromise,
      ])) as [any, any];

      minResult = mRes;
      dayResult = dRes;
    } catch (rlError) {
      console.warn("Upstash rate limit check bypassed due to network timeout or error:", rlError);
    }

    if (!minResult.success || !dayResult.success) {
      const errorMsg = !minResult.success
        ? "Rate limit exceeded: Maximum 5 requests per minute allowed."
        : "Rate limit exceeded: Maximum 100 requests per day allowed.";

      // Return SSE formatted error line so client UI displays standard rate limit message instantly
      const ssePayload = `data: ${JSON.stringify({ type: "error", error: errorMsg })}\n\n`;
      return new Response(ssePayload, {
        status: 429,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          "X-RateLimit-Limit-Min": minResult.limit.toString(),
          "X-RateLimit-Remaining-Min": minResult.remaining.toString(),
          "X-RateLimit-Limit-Day": dayResult.limit.toString(),
          "X-RateLimit-Remaining-Day": dayResult.remaining.toString(),
        },
      });
    }

    // Forward request to Python agent backend (http://localhost:8000/api/v1/agent/chat/stream)
    const backendResponse = await fetch(`${BACKEND_URL}/api/v1/agent/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    if (!backendResponse.ok) {
      const ssePayload = `data: ${JSON.stringify({
        type: "error",
        error: `Agent service error (${backendResponse.status}): ${backendResponse.statusText}`,
      })}\n\n`;
      return new Response(ssePayload, {
        status: backendResponse.status,
        headers: { "Content-Type": "text/event-stream" },
      });
    }

    // Return piped response stream back to client
    return new Response(backendResponse.body, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-RateLimit-Remaining-Min": minResult.remaining.toString(),
        "X-RateLimit-Remaining-Day": dayResult.remaining.toString(),
      },
    });
  } catch (error: any) {
    const ssePayload = `data: ${JSON.stringify({
      type: "error",
      error: `Proxy error: ${error.message || "Failed to reach agent service"}`,
    })}\n\n`;
    return new Response(ssePayload, {
      status: 500,
      headers: { "Content-Type": "text/event-stream" },
    });
  }
}
