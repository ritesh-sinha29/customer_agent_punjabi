"use client";

import {
  ArrowRight,
  LeafyGreen,
  Mic,
  Milk,
  Paperclip,
  Send,
  ShieldHalf,
  Sparkles,
  Syringe,
  Trash2,
  Vegan,
} from "lucide-react";
import type * as React from "react";
import { useState } from "react";
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
import { useSession } from "@/lib/auth-client";
import { SidebarTrigger } from "@/components/ui/sidebar";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

const SUGGESTIONS = [
  "ਗਾਂ ਜਾਂ ਮੱਝ ਵਿੱਚ ਦੁੱਧ ਬੁਖਾਰ (ਕੈਲਸ਼ੀਅਮ ਦੀ ਕਮੀ) ਤੋਂ ਕਿਵੇਂ ਬਚਿਆ ਜਾਵੇ?",
  "ਮੇਰੇ ਪਸ਼ੂ ਲਈ ਕਿਹੜਾ ਚਾਰਾ ਸਭ ਤੋਂ ਵਧੀਆ ਰਹੇਗਾ?",
  "ਦੁੱਧ ਦੀ ਕੁਆਲਟੀ ਅਤੇ ਫੈਟ ਕਿਵੇਂ ਵਧਾਈਏ?",
  "ਥਣੈਲਾ ਰੋਗ (ਮਾਸਟਾਈਟਿਸ) ਤੋਂ ਪਸ਼ੂਆਂ ਦਾ ਬਚਾਅ ਕਿਵੇਂ ਕਰੀਏ?",
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

export default function AiPage() {
  const { data: session } = useSession();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-transparent font-sans w-full relative">
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-white/20 to-white  pointer-events-none z-0" />

      {/* Top Header Bar with SidebarTrigger */}
      <header className="flex h-10 shrink-0 items-center justify-between px-6 pt-2 bg-transparent z-20 w-full">
        <SidebarTrigger className="-ml-1 text-[#2E3A2F] hover:bg-[#2E3A2F]/5" />
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
                      ਪੰਜਾਬ ਭਰ ਦੇ ਪਸ਼ੂ ਪਾਲਕਾਂ ਦਾ ਭਰੋਸੇਯੋਗ ਸਾਥੀ — ਉੱਚ-ਗੁਣਵੱਤਾ
                      ਪਸ਼ੂ ਪੋਸ਼ਣ ਅਤੇ ਵਿਗਿਆਨਕ ਤਰੀਕੇ ਨਾਲ ਤਿਆਰ ਕੀਤਾ ਸੰਤੁਲਿਤ ਚਾਰਾ।
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
                      {SUGGESTIONS.map((suggestion, index) => (
                        <button
                          key={suggestion}
                          type="button"
                          // onClick={() => handleSuggestionClick(suggestion)}
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
                <MessageScrollerContent className="max-w-3xl mx-auto w-full gap-6 pb-6">
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
                            <Avatar className="h-8 w-8 border border-zinc-200 bg-transparent">
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
                          <Bubble
                            variant={msg.role === "user" ? "default" : "muted"}
                          >
                            <BubbleContent
                              className={
                                msg.role === "user"
                                  ? "!bg-[#2E3A2F] !text-white"
                                  : ""
                              }
                            >
                              {msg.content}
                            </BubbleContent>
                          </Bubble>
                          <MessageFooter>{msg.timestamp}</MessageFooter>
                        </MessageContent>
                      </Message>
                    </MessageScrollerItem>
                  ))}

                  {isTyping && (
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
            // onSubmit={handleSend}
            className="relative flex flex-col rounded-2xl border border-[#2E3A2F]/20 bg-white p-3 shadow-md focus-within:border-[#2E3A2F] focus-within:ring-1 focus-within:ring-[#2E3A2F]/10 transition-all"
          >
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              // onKeyDown={handleKeyDown}
              placeholder="ਆਪਣਾ ਸਵਾਲ ਟਾਈਪ ਕਰੋ ਜਾਂ ਸੁਝਾਅ ਵਿੱਚੋਂ ਚੁਣੋ..."
              className="w-full bg-transparent border-none shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 outline-none resize-none py-2 px-2 min-h-[44px] max-h-32 text-sm text-zinc-800 disabled:opacity-50"
              disabled={isTyping}
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
                  disabled={isTyping}
                  title="Attach file (decorative)"
                >
                  <Paperclip className="w-4 h-4" />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 rounded-xl text-zinc-400 hover:text-zinc-600 hover:bg-[#2E3A2F]/5 cursor-pointer shrink-0"
                  disabled={isTyping}
                  title="Voice input (decorative)"
                >
                  <Mic className="w-4 h-4" />
                </Button>
              </div>

              {/* Right action */}
              <Button
                type="submit"
                disabled={!input.trim() || isTyping}
                className="h-9 px-4 bg-[#2E3A2F] text-white hover:bg-[#3E4E3F] transition-all rounded-full cursor-pointer disabled:opacity-40 shrink-0 flex items-center justify-center gap-1.5 text-xs font-semibold"
              >
                <span>ਭੇਜੋ</span>
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
            <span>
              ਇਹ AI ਸਲਾਹਕਾਰ ਸਿਰਫ਼ ਜਾਣਕਾਰੀ ਦੇਣ ਲਈ ਹੈ, ਕਿਰਪਾ ਕਰਕੇ ਵੈਟਰਨਰੀ ਡਾਕਟਰ ਦੀ
              ਸਲਾਹ ਵੀ ਲਵੋ।
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
