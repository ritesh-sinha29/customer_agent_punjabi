"use client";

import {
  ArrowRight,
  ChevronDown,
  Copy,
  LeafyGreen,
  Loader2,
  Mic,
  Milk,
  Paperclip,
  Send,
  ShieldHalf,
  Sparkles,
  Syringe,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  User,
  Vegan,
} from "lucide-react";
import type * as React from "react";
import { useState, useEffect, Suspense } from "react";
import { toast } from "sonner";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Bubble, BubbleContent } from "@/components/ui/bubble";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Marker, MarkerContent } from "@/components/ui/marker";
import {
  Message,
  MessageAvatar,
  MessageContent,
  MessageFooter,
} from "@/components/ui/message";
import {
  MessageScroller,
  MessageScrollerButton,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from "@/components/ui/message-scroller";
import { Textarea } from "@/components/ui/textarea";
import { signIn, signOut, useSession } from "@/lib/auth-client";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { useTypewriter } from "@/hooks/use-typewriter";
import { useAgentSSE } from "@/hooks/use-agent-sse";
import { MarkdownFormatter } from "@/components/ui/markdown-formatter";
import { useSearchParams, useRouter } from "next/navigation";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  reasoning?: string;
}

const SUGGESTIONS_EN = [
  "How can I prevent milk fever (calcium deficiency) in cows or buffaloes?",
  "Which fodder is best for my dairy cattle's nutrition?",
  "How can I increase the milk quality and fat content?",
  "How do I protect my cattle from mastitis?",
];

const SUGGESTIONS_PAN = [
  "ਗਾਂ ਜਾਂ ਮੱਝ ਵਿੱਚ ਮਿਲਕ ਫੀਵਰ (ਕੈਲਸ਼ੀਅਮ ਦੀ ਕਮੀ) ਤੋਂ ਕਿਵੇਂ ਬਚਾਅ ਕਰੀਏ?",
  "ਮੇਰੇ ਦੁੱਧ ਵਾਲੇ ਪਸ਼ੂਆਂ ਲਈ ਸਭ ਤੋਂ ਵਧੀਆ ਹਰਾ ਚਾਰਾ ਕਿਹੜਾ ਹੈ?",
  "ਦੁੱਧ ਦੀ ਗੁਣਵੱਤਾ ਅਤੇ ਫੈਟ ਪ੍ਰਤੀਸ਼ਤ ਕਿਵੇਂ ਵਧਾਇਆ ਜਾ ਸਕਦਾ ਹੈ?",
  "ਆਪਣੇ ਪਸ਼ੂਆਂ ਨੂੰ ਥਣਾਂ ਦੀ ਸੋਜ (ਮਾਸਟਾਈਟਿਸ) ਤੋਂ ਕਿਵੇਂ ਬਚਾਈਏ?",
];

const SUGGESTION_ICONS = [
  // Icon 0: Shield with plus (for calcium deficiency / milk fever)
  <ShieldHalf className="w-5 h-5 text-[#2E3A2F]" />,
  // Icon 1: Feed / milk bottle (for best fodder/feed)
  <Milk className="w-5 h-5 text-[#2E3A2F]" />,
  // Icon 2: Calf/goat face (for milk quality / fat / growth)
  <Vegan className="w-5 h-5 text-[#2E3A2F]" />,
  // Icon 3: Udder (for mastitis)
  <Syringe className="w-5 h-5 text-[#2E3A2F]" />,
];

function AiPageContent() {
  const { data: session } = useSession();
  const searchParams = useSearchParams();
  const router = useRouter();
  const urlThreadId = searchParams.get("threadId");

  const [input, setInput] = useState("");
  const [isRegistering, setIsRegistering] = useState(false);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [lang, setLang] = useState<"en" | "pan">("pan");

  const [threadId, setThreadId] = useState<string>(() => {
    return urlThreadId || `thread-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;
  });
  const userId = session?.user?.id || "guest_user";

  const { messages, setMessages, isLoading, pendingApproval, sendMessage, sendApproval } =
    useAgentSSE(threadId, userId);

  // Sync URL query parameter and threadId state
  useEffect(() => {
    if (!urlThreadId && threadId) {
      router.replace(`/ai?threadId=${threadId}`);
    } else if (urlThreadId && urlThreadId !== threadId) {
      setThreadId(urlThreadId);
    }
  }, [urlThreadId, threadId, router]);

  // Load message history from DB when active thread changes
  useEffect(() => {
    if (!threadId) return;

    let active = true;
    const fetchMessages = async () => {
      try {
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
        const res = await fetch(`${backendUrl}/api/v1/agent/threads/${threadId}/messages`);
        if (!res.ok) throw new Error("Failed to fetch messages");
        const data = await res.json();
        if (data.success && active) {
          setMessages(data.messages);
        }
      } catch (err) {
        console.error("Error fetching historical messages:", err);
      }
    };

    fetchMessages();

    return () => {
      active = false;
    };
  }, [threadId, setMessages]);

  const isTyping = isLoading;

  const suggestions = lang === "en" ? SUGGESTIONS_EN : SUGGESTIONS_PAN;
  const typedPlaceholder = useTypewriter(suggestions, 30, 15, 2000);

  const subheading =
    lang === "en"
      ? "Trusted companion of dairy farmers across Punjab — high-quality animal nutrition and scientifically formulated balanced feed."
      : "ਪੰਜਾਬ ਦੇ ਡੇਅਰੀ ਕਿਸਾਨਾਂ ਦਾ ਭਰੋਸੇਮੰਦ ਸਾਥੀ — ਉੱਚ ਗੁਣਵੱਤਾ ਵਾਲਾ ਪਸ਼ੂ ਪੋਸ਼ਣ ਅਤੇ ਵਿਗਿਆਨਕ ਢੰਗ ਨਾਲ ਤਿਆਰ ਕੀਤਾ ਸੰਤੁਲਿਤ ਪਸ਼ੂ ਆਹਾਰ।";

  const bottomDisclaimer =
    lang === "en"
      ? "This AI advisor is for informational purposes only. Please also consult a veterinarian."
      : "ਕਿਰਪਾ ਕਰਕੇ ਸਹੀ ਇਲਾਜ ਅਤੇ ਸਲਾਹ ਲਈ ਆਪਣੇ ਨਜ਼ਦੀਕੀ ਪਸ਼ੂ ਡਾਕਟਰ ਨਾਲ ਵੀ ਜ਼ਰੂਰ ਸੰਪਰਕ ਕਰੋ।";

  const handleSend = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || isLoading) return;

    sendMessage(input.trim());
    setInput("");
  };

  const handleCopy = async (content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      toast.success("Response copied to clipboard!");
    } catch (err) {
      console.error("Failed to copy text: ", err);
      toast.error("Failed to copy response.");
    }
  };

  const handleLike = (msgId: string) => {
    toast.success("Thank you for your feedback!", {
      description: "Response upvoted.",
    });
  };

  const handleDislike = (msgId: string) => {
    toast.success("Thank you for your feedback!", {
      description: "Response downvoted.",
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleGoogleSignIn = async () => {
    if (isRegistering) return;
    setIsRegistering(true);
    toast.loading("Connecting to Google...", {
      id: "google-login",
    });
    try {
      await signIn.social({
        provider: "google",
        callbackURL: window.location.href,
      });
    } catch (err) {
      console.error(err);
      toast.error("Google sign-in failed. Please try again.", {
        id: "google-login",
      });
      setIsRegistering(false);
    }
  };

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-transparent font-sans w-full relative">
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-white/20 to-white  pointer-events-none z-0" />

      {/* Top Header Bar with SidebarTrigger */}
      <header className="flex h-10 shrink-0 items-center justify-between px-6 pt-2 bg-transparent z-20 w-full">
        <SidebarTrigger className="-ml-1 text-[#2E3A2F] hover:bg-[#2E3A2F]/5" />

        <div className="flex items-center gap-4">
          {/* Language Toggle */}
          <div className="flex items-center bg-zinc-100/80 rounded-full p-0.5 border border-zinc-200/50 shadow-2xs">
            <button
              type="button"
              onClick={() => setLang("en")}
              className={`px-2.5 py-1 text-xs font-semibold rounded-full transition-all cursor-pointer ${
                lang === "en"
                  ? "bg-white text-[#2E3A2F] shadow-2xs"
                  : "text-zinc-500 hover:text-zinc-800"
              }`}
            >
              Eng
            </button>
            <button
              type="button"
              onClick={() => setLang("pan")}
              className={`px-2.5 py-1 text-xs font-semibold rounded-full transition-all cursor-pointer ${
                lang === "pan"
                  ? "bg-white text-[#2E3A2F] shadow-2xs"
                  : "text-zinc-500 hover:text-zinc-800"
              }`}
            >
              PAN
            </button>
          </div>

          {/* User Auth Section */}
          <div className="flex items-center gap-3">
            {session ? (
              <div className="relative">
                <button
                  onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                  className="flex items-center gap-2 hover:bg-zinc-50 px-2 py-1.5 rounded-full transition-all border border-zinc-100 cursor-pointer"
                >
                  <Avatar className="h-7 w-7 border border-zinc-200 shadow-2xs select-none">
                    <AvatarImage
                      src={session.user.image || undefined}
                      alt={session.user.name}
                    />
                    <AvatarFallback className="bg-[#2E3A2F]/10 text-[#2E3A2F] font-bold text-xs">
                      {session.user.name
                        ? session.user.name[0].toUpperCase()
                        : "U"}
                    </AvatarFallback>
                  </Avatar>
                  <span className="text-xs font-semibold text-[#2E3A2F] hidden sm:inline select-none">
                    {session.user.name}
                  </span>
                  <ChevronDown
                    className={`w-3.5 h-3.5 text-zinc-500 transition-transform duration-200 ${
                      isDropdownOpen ? "rotate-180" : ""
                    }`}
                  />
                </button>

                {isDropdownOpen && (
                  <>
                    <div
                      className="fixed inset-0 z-40 bg-transparent"
                      onClick={() => setIsDropdownOpen(false)}
                    />
                    <div className="absolute right-0 mt-2 w-40 bg-white rounded-lg shadow-lg border border-zinc-100 py-1.5 z-50 animate-in fade-in slide-in-from-top-2 duration-150 origin-top-right">
                      <button
                        onClick={async () => {
                          try {
                            await signOut({
                              fetchOptions: {
                                onSuccess: () => {
                                  window.location.reload();
                                },
                              },
                            });
                          } catch (err) {
                            console.error(err);
                          }
                        }}
                        className="w-full text-left px-4 py-2 text-xs font-medium text-red-600 hover:bg-red-50 transition-colors flex items-center gap-2 cursor-pointer"
                      >
                        Sign Out
                      </button>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <Avatar
                  className="h-8 w-8 border border-zinc-200 bg-zinc-100 flex items-center justify-center cursor-pointer hover:bg-zinc-200 transition-colors"
                  onClick={handleGoogleSignIn}
                >
                  <User className="w-4 h-4 text-zinc-500" />
                </Avatar>
                <Button
                  onClick={handleGoogleSignIn}
                  disabled={isRegistering}
                  className="bg-[#2E3A2F] text-white hover:bg-[#3E4E3F] rounded-full px-4 h-8 text-xs font-medium transition-all flex items-center gap-2"
                >
                  {isRegistering && (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  )}
                  Register
                </Button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Message Scroller occupies the whole space */}
      <div className="flex-1 min-h-0 relative w-full">
        <MessageScrollerProvider>
          <MessageScroller>
            <MessageScrollerViewport className="pt-0">
              {messages.length === 0 ? (
                <Empty className="border-0 bg-transparent flex flex-col items-center justify-start py-8 px-6 w-full h-auto">
                  <EmptyHeader className="!max-w-2xl">
                    <EmptyMedia variant="default" className="-mt-6 mx-auto ">
                      <img
                        src="/vrsa_logo.svg"
                        alt="VRSA Logo"
                        className="w-28 h-28 object-contain"
                      />
                    </EmptyMedia>
                    <EmptyTitle className="text-3xl font-semibold tracking-tight text-center">
                      VRSA Agrotech <span className="text-[#5F7560]">AI</span>{" "}
                      Advisor
                    </EmptyTitle>
                    <EmptyDescription className="text-emerald-900 text-base max-w-3xl mx-auto mt-2 text-center leading-relaxed">
                      {subheading}
                    </EmptyDescription>

                    {/* Leaf Separator */}
                    <div className="flex items-center gap-4 justify-center mt-4">
                      <div className="h-[2px] bg-emerald-800/10 w-16 rounded-full" />
                      <LeafyGreen className="w-5 h-5 text-[#5F7560] fill-[#5F7560]/20" />
                      <div className="h-[2px] bg-emerald-800/10 w-16 rounded-full" />
                    </div>
                  </EmptyHeader>

                  <div className="w-full max-w-4xl mt-8 z-10">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
                      {suggestions.map((suggestion, index) => (
                        <button
                          key={suggestion}
                          type="button"
                          onClick={() => setInput(suggestion)}
                          className="flex items-center justify-between p-2.5 rounded-lg border border-zinc-200 bg-neutral-50 hover:bg-emerald-700/10 transition-all duration-200 shadow-2xs group cursor-pointer w-full text-left"
                        >
                          <div className="flex items-center gap-4 flex-1 pr-2">
                            {/* Icon Circle Wrapper */}
                            <div className="h-10 w-10 rounded-full bg-green-700/20 flex items-center justify-center shrink-0">
                              {SUGGESTION_ICONS[index] || (
                                <Sparkles className="w-4 h-4 text-[#2E3A2F]" />
                              )}
                            </div>
                            <span className="text-[13px] font-medium text-[#2E3A2F] leading-snug">
                              {suggestion}
                            </span>
                          </div>

                          {/* Right Arrow Circle */}
                          <div className="h-8 w-8 rounded-full border border-zinc-200 flex items-center justify-center shrink-0 text-zinc-400 group-hover:text-[#2E3A2F] group-hover:border-zinc-300 transition-all bg-white shadow-2xs">
                            <ArrowRight className="w-4 h-4" />
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                </Empty>
              ) : (
                <MessageScrollerContent className="max-w-3xl mx-auto w-full gap-6 pt-10 pb-6">
                  {messages.map((msg) => (
                    <MessageScrollerItem key={msg.id}>
                      <Message align={msg.role === "user" ? "end" : "start"}>
                        <MessageAvatar>
                          {msg.role === "user" ? (
                            <Avatar className="h-8 w-8 border border-zinc-200">
                              <AvatarImage
                                src={session?.user?.image || undefined}
                                alt="User"
                              />
                              <AvatarFallback className="bg-zinc-100 text-[#2E3A2F] font-bold text-xs">
                                {session?.user?.name
                                  ? session.user.name[0].toUpperCase()
                                  : "U"}
                              </AvatarFallback>
                            </Avatar>
                          ) : (
                            <Avatar className="h-8 w-8 ">
                              <AvatarImage
                                src="/vrsa_logo.svg"
                                alt="VRSA Logo"
                                className="object-contain p-1"
                              />
                              <AvatarFallback className="bg-transparent text-[#2E3A2F] font-bold text-xs">
                                VRSA
                              </AvatarFallback>
                            </Avatar>
                          )}
                        </MessageAvatar>
                        <MessageContent>
                          {msg.role === "assistant" && (
                            <>
                              {/* Thinking phase (ONLY visible while executing and before response content arrives) */}
                              {isLoading &&
                                msg.id === messages[messages.length - 1]?.id &&
                                !msg.content && (
                                  <div className="mb-2 w-full max-w-full">
                                    <details
                                      open
                                      className="group text-xs text-emerald-800 bg-emerald-50/60 border border-emerald-200/80 rounded-xl p-3 select-none transition-all shadow-2xs"
                                    >
                                      <summary className="cursor-pointer flex items-center justify-between list-none outline-none [&::-webkit-details-marker]:hidden">
                                        <div className="flex items-center gap-2">
                                          <Loader2 className="w-3.5 h-3.5 text-emerald-600 animate-spin shrink-0" />
                                          <span className="font-bold text-emerald-900">
                                            Thinking...
                                          </span>
                                        </div>
                                        <ChevronDown className="w-4 h-4 text-emerald-600 transition-transform duration-200 group-open:rotate-180" />
                                      </summary>
                                      <div className="mt-2 text-zinc-700 font-medium whitespace-pre-wrap leading-relaxed select-text">
                                        {msg.reasoning || "Analyzing query & consulting knowledge base..."}
                                      </div>
                                    </details>
                                  </div>
                                )}
                            </>
                          )}
                          {msg.approvalCard && (
                            <div className="mb-2.5 w-full max-w-md mx-auto">
                              <div
                                className={`flex flex-col gap-1.5 p-3.5 rounded-2xl text-xs border shadow-2xs transition-all ${
                                  msg.approvalCard.status === "approved"
                                    ? "bg-emerald-50/90 border-emerald-200/80 text-emerald-900"
                                    : "bg-zinc-50 border-zinc-200 text-zinc-600"
                                }`}
                              >
                                <div className="flex items-center gap-2 font-bold text-xs">
                                  {msg.approvalCard.status === "approved" ? (
                                    <>
                                      <span className="h-2 w-2 rounded-full bg-emerald-600" />
                                      <span>
                                        {msg.approvalCard.action === "booking"
                                          ? "✓ Booking Confirmed"
                                          : "✓ Support Request Submitted"}
                                      </span>
                                    </>
                                  ) : (
                                    <>
                                      <span className="h-2 w-2 rounded-full bg-zinc-400" />
                                      <span>
                                        {msg.approvalCard.action === "booking"
                                          ? "✕ Booking Cancelled"
                                          : "✕ Support Request Cancelled"}
                                      </span>
                                    </>
                                  )}
                                </div>
                                <div className="text-[11px] opacity-90 space-y-0.5 mt-0.5 bg-white/50 p-2 rounded-lg border border-black/5">
                                  <div>
                                    <strong>
                                      {lang === "en" ? "Product" : "ਉਤਪਾਦ"}:
                                    </strong>{" "}
                                    {msg.approvalCard.details?.product_name}
                                  </div>
                                  <div>
                                    <strong>
                                      {lang === "en" ? "Quantity" : "ਮਾਤਰਾ"}:
                                    </strong>{" "}
                                    {msg.approvalCard.details?.quantity}
                                  </div>
                                </div>
                              </div>
                            </div>
                          )}
                          {msg.content && (
                            <Bubble
                              variant={
                                msg.role === "user" ? "default" : "muted"
                              }
                            >
                              <BubbleContent
                                className={
                                  msg.role === "user"
                                    ? "!bg-[#2E3A2F] !text-white"
                                    : ""
                                }
                              >
                                {msg.role === "user" ? (
                                  msg.content
                                ) : (
                                  <MarkdownFormatter content={msg.content} />
                                )}
                              </BubbleContent>
                            </Bubble>
                          )}
                          <MessageFooter className="flex items-center gap-3 w-full mt-0.5 min-h-[24px]">
                            <div className="flex items-center gap-2 text-neutral-700 text-xs font-medium">
                              <span>{msg.timestamp}</span>
                              {msg.duration !== undefined && (
                                <span>
                                  • Executed in {msg.duration.toFixed(1)}s
                                </span>
                              )}
                            </div>
                            {msg.role === "assistant" && msg.content && (
                              <div className="flex items-center gap-0.5 ">
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon"
                                  className="h-6 w-6 rounded-md text-zinc-600 hover:text-zinc-600 hover:bg-zinc-100 cursor-pointer shrink-0"
                                  onClick={() => handleCopy(msg.content)}
                                  title="Copy response"
                                >
                                  <Copy className="w-3 h-3" />
                                </Button>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon"
                                  className="h-6 w-6 rounded-md text-zinc-600 hover:text-zinc-600 hover:bg-zinc-100 cursor-pointer shrink-0"
                                  onClick={() => handleLike(msg.id)}
                                  title="Like response"
                                >
                                  <ThumbsUp className="w-3 h-3" />
                                </Button>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon"
                                  className="h-6 w-6 rounded-md text-zinc-600 hover:text-zinc-600 hover:bg-zinc-100 cursor-pointer shrink-0"
                                  onClick={() => handleDislike(msg.id)}
                                  title="Dislike response"
                                >
                                  <ThumbsDown className="w-3 h-3" />
                                </Button>
                              </div>
                            )}
                          </MessageFooter>
                        </MessageContent>
                      </Message>
                    </MessageScrollerItem>
                  ))}

                  {pendingApproval && (
                    <MessageScrollerItem>
                      <div className="flex flex-col gap-3 p-4 bg-emerald-50/50 border border-emerald-200/60 rounded-2xl max-w-md mx-auto my-3 shadow-2xs">
                        <div className="flex items-center gap-2">
                          <span className="h-2 w-2 rounded-full bg-emerald-600 animate-pulse" />
                          <p className="text-xs font-bold text-emerald-800">
                            {lang === "en"
                              ? "Action Required"
                              : "ਕਾਰਵਾਈ ਦੀ ਲੋੜ ਹੈ"}
                          </p>
                        </div>
                        <div className="text-xs text-zinc-700 space-y-1 bg-white/60 p-2.5 rounded-lg border border-zinc-100">
                          {pendingApproval.action === "booking" ? (
                            <div>
                              <strong>
                                {lang === "en" ? "Product" : "ਉਤਪਾਦ"}:
                              </strong>{" "}
                              {pendingApproval.details?.product_name}
                              <br />
                              <strong>
                                {lang === "en" ? "Quantity" : "ਮਾਤਰਾ"}:
                              </strong>{" "}
                              {pendingApproval.details?.quantity}
                            </div>
                          ) : (
                            <div>
                              <strong>
                                {lang === "en" ? "Title" : "ਸਿਰਲੇਖ"}:
                              </strong>{" "}
                              {pendingApproval.details?.title}
                              <br />
                              <strong>
                                {lang === "en" ? "Description" : "ਵੇਰਵਾ"}:
                              </strong>{" "}
                              {pendingApproval.details?.description}
                            </div>
                          )}
                        </div>
                        <div className="flex gap-2 justify-end">
                          <button
                            type="button"
                            onClick={() => sendApproval(false)}
                            className="px-3.5 py-1.5 border border-zinc-200 bg-white hover:bg-red-50 hover:text-red-600 text-zinc-600 rounded-full text-xs font-semibold cursor-pointer transition-all"
                          >
                            {lang === "en" ? "Cancel" : "ਰੱਦ ਕਰੋ"}
                          </button>
                          <button
                            type="button"
                            onClick={() => sendApproval(true)}
                            className="px-3.5 py-1.5 bg-[#2E3A2F] hover:bg-[#3E4E3F] text-white rounded-full text-xs font-semibold cursor-pointer transition-all shadow-3xs"
                          >
                            {lang === "en"
                              ? "Confirm & Proceed"
                              : "ਪੁਸ਼ਟੀ ਕਰੋ ਅਤੇ ਅੱਗੇ ਵਧੋ"}
                          </button>
                        </div>
                      </div>
                    </MessageScrollerItem>
                  )}

                  {isTyping &&
                    messages[messages.length - 1]?.role !== "assistant" && (
                      <MessageScrollerItem>
                        <Message align="start">
                          <MessageAvatar>
                            <Avatar className="h-8 w-8 border border-zinc-200 bg-transparent animate-pulse">
                              <AvatarImage
                                src="/vrsa_logo.svg"
                                alt="VRSA Logo"
                                className="object-contain p-1"
                              />
                              <AvatarFallback className="bg-transparent text-[#2E3A2F] font-bold text-xs">
                                VRSA
                              </AvatarFallback>
                            </Avatar>
                          </MessageAvatar>
                          <MessageContent>
                            <Marker>
                              <MarkerContent className="flex items-center gap-1.5 px-3 py-2 bg-zinc-100 rounded-2xl w-fit">
                                <span className="flex h-1.5 w-1.5 rounded-full bg-zinc-400 animate-bounce [animation-delay:-0.3s]" />
                                <span className="flex h-1.5 w-1.5 rounded-full bg-zinc-400 animate-bounce [animation-delay:-0.15s]" />
                                <span className="flex h-1.5 w-1.5 rounded-full bg-zinc-400 animate-bounce" />
                              </MarkerContent>
                            </Marker>
                          </MessageContent>
                        </Message>
                      </MessageScrollerItem>
                    )}
                  {/* Scroll anchor */}
                  <MessageScrollerItem
                    scrollAnchor={true}
                    className="h-0 min-h-0"
                  />
                </MessageScrollerContent>
              )}
            </MessageScrollerViewport>
            <MessageScrollerButton direction="end" />
          </MessageScroller>
        </MessageScrollerProvider>
      </div>

      {/* Textarea fixed at the bottom, centered */}
      <div className="bg-transparent pb-4 px-4 md:px-6 shrink-0 w-full z-10">
        <div className="max-w-3xl mx-auto w-full">
          <form
            onSubmit={handleSend}
            className="relative flex flex-col rounded-2xl border border-[#2E3A2F]/20 bg-white p-3 shadow-md focus-within:border-[#2E3A2F] focus-within:ring-1 focus-within:ring-[#2E3A2F]/10 transition-all"
          >
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                pendingApproval
                  ? lang === "en"
                    ? "Please confirm or cancel the action above..."
                    : "ਕਿਰਪਾ ਕਰਕੇ ਉੱਪਰ ਦਿੱਤੀ ਕਾਰਵਾਈ ਦੀ ਪੁਸ਼ਟੀ ਜਾਂ ਰੱਦ ਕਰੋ..."
                  : typedPlaceholder ||
                    (lang === "en"
                      ? "Type your question or choose from suggestions..."
                      : "ਆਪਣਾ ਸਵਾਲ ਲਿਖੋ ਜਾਂ ਹੇਠਾਂ ਦਿੱਤੇ ਸੁਝਾਵਾਂ ਵਿੱਚੋਂ ਚੁਣੋ...")
              }
              className="w-full bg-transparent border-none shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 outline-none resize-none py-2 px-2 min-h-[44px] max-h-32 text-sm text-zinc-800 disabled:opacity-50"
              disabled={isLoading || !!pendingApproval}
            />

            {/* Actions row below */}
            <div className="flex items-center justify-between border-t border-zinc-100/50 pt-2 mt-1 px-1">
              {/* Left actions */}
              <div className="flex items-center gap-1.5">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 rounded-xl text-zinc-400 hover:text-zinc-600 hover:bg-[#2E3A2F]/5 cursor-pointer shrink-0"
                  disabled={isLoading || !!pendingApproval}
                  title="Attach file (decorative)"
                >
                  <Paperclip className="w-4 h-4" />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 rounded-xl text-zinc-400 hover:text-zinc-600 hover:bg-[#2E3A2F]/5 cursor-pointer shrink-0"
                  disabled={isLoading || !!pendingApproval}
                  title="Voice input (decorative)"
                >
                  <Mic className="w-4 h-4" />
                </Button>
              </div>

              {/* Right action */}
              <Button
                type="submit"
                disabled={!input.trim() || isLoading || !!pendingApproval}
                className="h-9 px-4 bg-[#2E3A2F] text-white hover:bg-[#3E4E3F] transition-all rounded-full cursor-pointer disabled:opacity-40 shrink-0 flex items-center justify-center gap-1.5 text-xs font-semibold"
              >
                <span>Send</span>
                <Send className="w-3.5 h-3.5" />
              </Button>
            </div>
          </form>

          {/* Warning disclaimer below input form */}
          <div className="mt-3 text-center flex items-center justify-center gap-1 text-[11px] text-zinc-500">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              className="w-3.5 h-3.5 text-zinc-400 shrink-0"
            >
              <path
                d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M12 16v-4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M12 8h.01"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <span>{bottomDisclaimer}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AiPage() {
  return (
    <Suspense fallback={null}>
      <AiPageContent />
    </Suspense>
  );
}
