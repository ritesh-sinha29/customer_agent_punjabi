"use client";

import {
  ArrowRight,
  ChevronDown,
  Copy,
  Languages,
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
import { useRouter, useSearchParams } from "next/navigation";
import type * as React from "react";
import { Suspense, useEffect, useRef, useState } from "react";
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
import { MarkdownFormatter } from "@/components/ui/markdown-formatter";
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
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Textarea } from "@/components/ui/textarea";
import { useAgentSSE } from "@/hooks/use-agent-sse";
import { useTypewriter } from "@/hooks/use-typewriter";
import { signIn, signOut, useSession } from "@/lib/auth-client";
import { LiveWaveform } from "@/modules/ai/live-waveform";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  reasoning?: string;
  duration?: number;
  memoryUpdated?: boolean;
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
  const [translations, setTranslations] = useState<
    Record<
      string,
      { text: string; loading: boolean; showTranslated: boolean; error?: boolean }
    >
  >({});

  // Voice STT Recording States
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const handleMicClick = async () => {
    if (isTranscribing) return;

    if (isRecording) {
      if (
        mediaRecorderRef.current &&
        mediaRecorderRef.current.state !== "inactive"
      ) {
        mediaRecorderRef.current.stop();
      }
      setIsRecording(false);
      return;
    }

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        toast.error("Microphone access is not supported in your browser.");
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : undefined,
      });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());

        if (audioChunksRef.current.length === 0) {
          toast.error("No audio recorded.");
          return;
        }

        const audioBlob = new Blob(audioChunksRef.current, {
          type: mediaRecorder.mimeType || "audio/webm",
        });

        setIsTranscribing(true);
        const toastId = toast.loading(
          lang === "en"
            ? "Transcribing & translating your voice to English..."
            : "ਤੁਹਾਡੀ ਆਵਾਜ਼ ਨੂੰ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ ਬਦਲਿਆ ਜਾ ਰਿਹਾ ਹੈ...",
        );

        try {
          const formData = new FormData();
          formData.append("audio", audioBlob, "audio.webm");

          const res = await fetch("/api/stt", {
            method: "POST",
            body: formData,
          });

          const data = await res.json();

          if (!res.ok || !data.success) {
            throw new Error(data.error || "Speech transcription failed.");
          }

          if (data.text) {
            console.log("🎤 Transcribed text output:", data.text);
            setInput((prev) => (prev ? `${prev} ${data.text}` : data.text));
            toast.success(
              lang === "en"
                ? "Converted to English!"
                : "ਆਵਾਜ਼ ਸਫਲਤਾਪੂਰਵਕ ਅੰਗਰੇਜ਼ੀ 'ਚ ਤਬਦੀਲ ਹੋ ਗਈ!",
              { id: toastId },
            );
          } else {
            toast.error("Could not recognize any spoken text.", {
              id: toastId,
            });
          }
        } catch (err: any) {
          console.error("STT Error:", err);
          toast.error(err.message || "Failed to transcribe audio.", {
            id: toastId,
          });
        } finally {
          setIsTranscribing(false);
        }
      };

      mediaRecorder.start();
      setIsRecording(true);
      toast.info(
        lang === "en"
          ? "Listening... Speak in Punjabi, Hindi or English. Click mic again to finish."
          : "ਸੁਣ ਰਿਹਾ ਹੈ... ਪੰਜਾਬੀ, ਹਿੰਦੀ ਜਾਂ ਅੰਗਰੇਜ਼ੀ ਵਿੱਚ ਬੋਲੋ। ਪੂਰਾ ਹੋਣ 'ਤੇ ਮਾਈਕ 'ਤੇ ਕਲਿੱਕ ਕਰੋ।",
      );
    } catch (err) {
      console.error("Microphone access error:", err);
      toast.error("Microphone permission denied or unavailable.");
    }
  };

  const [threadId, setThreadId] = useState<string>(() => {
    return (
      urlThreadId ||
      `thread-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`
    );
  });
  const userId = session?.user?.id || "guest_user";

  const {
    messages,
    setMessages,
    isLoading,
    pendingApproval,
    sendMessage,
    sendApproval,
  } = useAgentSSE(threadId, userId);

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
        const backendUrl =
          process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
        const res = await fetch(
          `${backendUrl}/api/v1/agent/threads/${threadId}/messages`,
        );
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

  const handleCopy = async (content: string, isUser = false) => {
    try {
      await navigator.clipboard.writeText(content);
      toast.success(
        isUser ? "Message copied to clipboard!" : "Response copied to clipboard!",
      );
    } catch (err) {
      console.error("Failed to copy text: ", err);
      toast.error("Failed to copy text.");
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

  const handleTranslate = async (msgId: string, content: string) => {
    if (translations[msgId]?.showTranslated) {
      setTranslations((prev) => ({
        ...prev,
        [msgId]: { ...prev[msgId], showTranslated: false },
      }));
      return;
    }

    if (translations[msgId]?.text) {
      setTranslations((prev) => ({
        ...prev,
        [msgId]: { ...prev[msgId], showTranslated: true },
      }));
      return;
    }

    setTranslations((prev) => ({
      ...prev,
      [msgId]: { text: "", loading: true, showTranslated: false, error: false },
    }));

    try {
      const backendUrl =
        process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

      // 25 second timeout controller for Temporal execution allowance
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 25000);

      const res = await fetch(`${backendUrl}/api/v1/agent/translate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: content }),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      const data = await res.json();
      if (res.ok && data.translated_text) {
        setTranslations((prev) => ({
          ...prev,
          [msgId]: {
            text: data.translated_text,
            loading: false,
            showTranslated: true,
            error: false,
          },
        }));
        toast.success("Translated message to Punjabi!");
      } else {
        throw new Error(data.detail || data.error || "Translation failed");
      }
    } catch (err: any) {
      console.error("Translation error:", err);
      const isTimeout = err.name === "AbortError";
      toast.error(
        isTimeout
          ? "Translation timed out (25s limit). Click Retry to try again."
          : "Translation failed. Click Retry to try again.",
      );
      setTranslations((prev) => ({
        ...prev,
        [msgId]: { text: "", loading: false, showTranslated: false, error: true },
      }));
    }
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
                                        {msg.reasoning ||
                                          "Analyzing query & consulting knowledge base..."}
                                      </div>
                                    </details>
                                  </div>
                                )}
                            </>
                          )}
                          {msg.approvalCard && (
                            <div className="mb-2.5 w-full ">
                              <details className="group rounded-xl bg-neutral-100/90 border border-neutral-200/80 p-3 text-xs text-neutral-800 transition-all select-none shadow-2xs">
                                <summary className="cursor-pointer flex items-center justify-between list-none font-medium outline-none [&::-webkit-details-marker]:hidden">
                                  <div className="flex items-center gap-2">
                                    <span
                                      className={`h-2 w-2 rounded-full ${
                                        msg.approvalCard.status === "approved"
                                          ? "bg-emerald-600"
                                          : "bg-zinc-400"
                                      }`}
                                    />
                                    <span className="font-semibold text-neutral-900 text-xs">
                                      {msg.approvalCard.status === "approved"
                                        ? msg.approvalCard.action === "booking"
                                          ? lang === "en"
                                            ? "Booking Confirmed for VRSA Agrotech Products"
                                            : "VRSA Agrotech ਉਤਪਾਦਾਂ ਦੀ ਪੁਸ਼ਟੀ ਹੋ ਗਈ ਹੈ"
                                          : lang === "en"
                                            ? "Support Request Submitted"
                                            : "ਸਹਾਇਤਾ ਬੇਨਤੀ ਦਰਜ ਕੀਤੀ ਗਈ ਹੈ"
                                        : msg.approvalCard.action === "booking"
                                          ? lang === "en"
                                            ? "Booking Request Cancelled"
                                            : "ਬੁਕਿੰਗ ਬੇਨਤੀ ਰੱਦ ਕੀਤੀ ਗਈ ਹੈ"
                                          : lang === "en"
                                            ? "Support Request Cancelled"
                                            : "ਸਹਾਇਤਾ ਬੇਨਤੀ ਰੱਦ ਕੀਤੀ ਗਈ ਹੈ"}
                                    </span>
                                  </div>
                                  <ChevronDown className="w-4 h-4 text-neutral-500 transition-transform duration-200 group-open:rotate-180 shrink-0" />
                                </summary>
                                <div className="mt-2.5 pt-2.5 border-t border-neutral-200/80 text-[11px] text-neutral-700 space-y-1 bg-white/70 p-2.5 rounded-lg border border-neutral-200/40 select-text">
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
                              </details>
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
                                  <div>
                                    {translations[msg.id]?.showTranslated ? (
                                      <>
                                        <div className="mb-1.5 inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200/80 shadow-2xs">
                                          <Languages className="w-3 h-3 text-emerald-600" />
                                          ਅਨੁਵਾਦ (Punjabi Translation)
                                        </div>
                                        <MarkdownFormatter
                                          content={translations[msg.id].text}
                                        />
                                      </>
                                    ) : (
                                      <MarkdownFormatter content={msg.content} />
                                    )}
                                  </div>
                                )}
                              </BubbleContent>
                            </Bubble>
                          )}
                          <MessageFooter className="flex items-center gap-3 w-full mt-0.5 min-h-[24px]">
                            <div className="flex items-center gap-1.5 text-neutral-700 text-xs font-medium">
                              {msg.role === "user" && msg.content && (
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon"
                                  className="h-5 w-5 rounded-md text-zinc-500 hover:text-zinc-800 hover:bg-zinc-100 cursor-pointer shrink-0 transition-colors"
                                  onClick={() => handleCopy(msg.content, true)}
                                  title="Copy message"
                                >
                                  <Copy className="w-3 h-3" />
                                </Button>
                              )}
                              <span>{msg.timestamp}</span>
                              {msg.duration !== undefined && (
                                <span>
                                  • Executed in {msg.duration.toFixed(1)}s
                                </span>
                              )}
                              {msg.memoryUpdated && (
                                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200/80 shadow-2xs">
                                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-600 animate-pulse" />
                                  Memory Updated
                                </span>
                              )}
                            </div>
                            {msg.role === "assistant" && msg.content && (
                              <div className="flex items-center gap-1">
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  className={`h-6 px-2 rounded-md text-xs font-medium cursor-pointer shrink-0 transition-all ${
                                    translations[msg.id]?.error
                                      ? "bg-amber-50 text-amber-800 border border-amber-300 hover:bg-amber-100"
                                      : translations[msg.id]?.showTranslated
                                        ? "bg-emerald-100 text-emerald-800 border border-emerald-300 hover:bg-emerald-200"
                                        : "text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100"
                                  }`}
                                  onClick={() =>
                                    handleTranslate(msg.id, msg.content)
                                  }
                                  title={
                                    translations[msg.id]?.error
                                      ? "Click to retry translation"
                                      : "Translate message to Punjabi"
                                  }
                                >
                                  {translations[msg.id]?.loading ? (
                                    <Loader2 className="w-3 h-3 animate-spin text-emerald-700" />
                                  ) : translations[msg.id]?.error ? (
                                    <span className="flex items-center gap-1 text-[11px] font-semibold text-amber-800">
                                      <Languages className="w-3.5 h-3.5" />
                                      ਮੁੜ ਕੋਸ਼ਿਸ਼ (Retry)
                                    </span>
                                  ) : (
                                    <span className="flex items-center gap-1 text-[11px] font-semibold">
                                      <Languages className="w-3.5 h-3.5" />
                                      {translations[msg.id]?.showTranslated
                                        ? "English"
                                        : "ਅਨੁਵਾਦ (PA)"}
                                    </span>
                                  )}
                                </Button>
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
                  onClick={handleMicClick}
                  className={`h-8 w-8 rounded-xl transition-all cursor-pointer shrink-0 relative ${
                    isRecording
                      ? "bg-red-100 text-red-600 hover:bg-red-200 border border-red-300"
                      : isTranscribing
                        ? "bg-emerald-50 text-emerald-700"
                        : "text-zinc-400 hover:text-zinc-600 hover:bg-[#2E3A2F]/5"
                  }`}
                  disabled={isLoading || !!pendingApproval || isTranscribing}
                  title={
                    isRecording
                      ? "Click to stop & transcribe"
                      : isTranscribing
                        ? "Transcribing voice..."
                        : "Voice input (Speak in Punjabi / Hindi / English)"
                  }
                >
                  {isTranscribing ? (
                    <Loader2 className="w-4 h-4 animate-spin text-emerald-700" />
                  ) : isRecording ? (
                    <span className="relative flex items-center justify-center">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
                      <Mic className="w-4 h-4 text-red-600 relative z-10" />
                    </span>
                  ) : (
                    <Mic className="w-4 h-4" />
                  )}
                </Button>
              </div>

              {/* Centered waveform */}
              {(isRecording || isTranscribing) && (
                <div className="flex-1 max-w-[200px] mx-4 h-9 flex items-center justify-center">
                  <LiveWaveform
                    active={isRecording}
                    processing={isTranscribing}
                    mode="static"
                    height={28}
                    barColor={isRecording ? "#ef4444" : "#10b981"}
                  />
                </div>
              )}

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
