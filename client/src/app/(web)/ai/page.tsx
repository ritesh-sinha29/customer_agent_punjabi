"use client";

import { Bot, Mic, Paperclip, Send, Sparkles, Trash2 } from "lucide-react";
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

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

const SUGGESTIONS = [
  "What cattle feed is best for maximizing milk production?",
  "How can I prevent calcium deficiency (milk fever) in cows?",
  "Which veterinary medicines are recommended for mastitis?",
  "What nutritional supplements are best for growing calves?",
];

export default function AiPage() {
  const { data: session } = useSession();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);

  const formatTime = () => {
    return new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const simulateAIResponse = (userQuery: string) => {
    setIsTyping(true);

    let reply =
      "Hello! I am your VRSA Agrotech AI Assistant. Currently, my backend agent service is not connected, but I am ready to handle queries regarding cattle feed, veterinary medicines, and nutrition once the routes are established.";

    const queryLower = userQuery.toLowerCase();
    if (
      queryLower.includes("milk") ||
      queryLower.includes("feed") ||
      queryLower.includes("maximize")
    ) {
      reply =
        "For maximizing milk production, we recommend our VRSA Premium Cattle Feed. It contains balanced proteins, fats, and essential minerals to improve rumen fermentation and boost milk yield. Once our backend agent is configured, I can customize a complete feeding schedule for your herd.";
    } else if (
      queryLower.includes("fever") ||
      queryLower.includes("calcium") ||
      queryLower.includes("deficiency")
    ) {
      reply =
        "Calcium deficiency (milk fever) in pregnant cows can be prevented by maintaining a proper dietary cation-anion difference (DCAD) during the dry period and providing oral calcium supplements immediately post-calving. When our AI agent backend is connected, I can help diagnose specific symptoms.";
    } else if (
      queryLower.includes("mastitis") ||
      queryLower.includes("treatment") ||
      queryLower.includes("medicine")
    ) {
      reply =
        "Mastitis is a bacterial infection of the udder. Immediate treatment with intramammary antibiotics and anti-inflammatory medications is recommended under veterinary supervision. milker hygiene and post-milking teat dipping are key prevention steps. Once our backend is online, I will be able to retrieve our catalog and recommend matching veterinary medicines.";
    } else if (
      queryLower.includes("supplement") ||
      queryLower.includes("calf") ||
      queryLower.includes("growth")
    ) {
      reply =
        "Growing calves need a high-protein starter feed along with calf growth supplements containing vitamins A, D3, E, and trace minerals like zinc and selenium. Let's connect our backend database next to suggest the exact products in our store!";
    }

    setTimeout(() => {
      const botMsg: ChatMessage = {
        id: Math.random().toString(36).substring(7),
        role: "assistant",
        content: reply,
        timestamp: formatTime(),
      };
      setMessages((prev) => [...prev, botMsg]);
      setIsTyping(false);
    }, 1200);
  };

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isTyping) return;

    const userMsg: ChatMessage = {
      id: Math.random().toString(36).substring(7),
      role: "user",
      content: input.trim(),
      timestamp: formatTime(),
    };

    setMessages((prev) => [...prev, userMsg]);
    const currentInput = input.trim();
    setInput("");

    simulateAIResponse(currentInput);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend(e);
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    if (isTyping) return;

    const userMsg: ChatMessage = {
      id: Math.random().toString(36).substring(7),
      role: "user",
      content: suggestion,
      timestamp: formatTime(),
    };

    setMessages((prev) => [...prev, userMsg]);
    simulateAIResponse(suggestion);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-70px)] overflow-hidden bg-white font-sans w-full relative">
      {/* Floating Clear Chat Button */}
      {messages.length > 0 && (
        <div className="absolute top-4 right-4 z-20">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setMessages([])}
            className="text-xs text-zinc-500 hover:text-zinc-700 hover:bg-zinc-50 border-zinc-200 rounded-xl gap-1.5 h-8 px-3 bg-white/90 backdrop-blur-xs shadow-2xs"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Clear Chat</span>
          </Button>
        </div>
      )}

      {/* Message Scroller occupies the whole space */}
      <div className="flex-1 min-h-0 relative w-full">
        <MessageScrollerProvider>
          <MessageScroller>
            <MessageScrollerViewport className="p-4 md:p-8">
              {messages.length === 0 ? (
                <Empty className="border-0 bg-transparent flex flex-col justify-center items-center py-16 px-6 h-full min-h-full">
                  <EmptyHeader>
                    <EmptyMedia
                      variant="icon"
                      className="bg-[#2E3A2F]/10 text-[#2E3A2F] h-16 w-16 rounded-2xl flex items-center justify-center mb-4 mx-auto"
                    >
                      <Bot className="w-8 h-8 text-[#2E3A2F]" />
                    </EmptyMedia>
                    <EmptyTitle className="text-2xl font-bold tracking-tight text-[#2E3A2F] mt-2 text-center">
                      VRSA Agrotech AI Advisor
                    </EmptyTitle>
                    <EmptyDescription className="text-zinc-500 text-sm max-w-sm mx-auto mt-2 text-center">
                      Welcome to your AI assistant. Ask any questions about
                      cattle feed, nutrition, diseases, treatments, or
                      supplements.
                    </EmptyDescription>
                  </EmptyHeader>

                  <EmptyContent className="w-full max-w-3xl mt-12">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 w-full">
                      {SUGGESTIONS.map((suggestion) => (
                        <button
                          key={suggestion}
                          type="button"
                          onClick={() => handleSuggestionClick(suggestion)}
                          className="text-left p-5 rounded-xl border border-zinc-200/80 bg-white hover:bg-zinc-50 hover:border-zinc-300 transition-all duration-200 shadow-2xs group cursor-pointer"
                        >
                          <div className="text-xs font-semibold text-[#2E3A2F] mb-1.5 flex items-center gap-1.5">
                            <Sparkles className="w-3.5 h-3.5 text-[#5F7560]" />
                            <span>Suggestion</span>
                          </div>
                          <p className="text-xs text-zinc-600 leading-relaxed">
                            {suggestion}
                          </p>
                        </button>
                      ))}
                    </div>
                  </EmptyContent>
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
                            <Avatar className="h-8 w-8 border border-zinc-200 bg-[#2E3A2F]/10">
                              <AvatarFallback className="bg-[#2E3A2F]/10 text-[#2E3A2F] font-bold text-xs">
                                <Bot className="w-4 h-4 text-[#2E3A2F]" />
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
                          <Avatar className="h-8 w-8 border border-zinc-200 bg-[#2E3A2F]/10 animate-pulse">
                            <AvatarFallback className="bg-[#2E3A2F]/10 text-[#2E3A2F] font-bold text-xs">
                              <Bot className="w-4 h-4 text-[#2E3A2F]" />
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
      <div className="border-t border-zinc-100 bg-white p-4 md:p-6 shrink-0 w-full">
        <div className="max-w-3xl mx-auto w-full">
          <form
            onSubmit={handleSend}
            className="relative flex flex-col rounded-2xl border border-zinc-200 bg-zinc-50/30 p-2.5 focus-within:border-zinc-300 focus-within:ring-1 focus-within:ring-zinc-300 transition-all"
          >
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type a message or select a suggestion..."
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
                  className="h-8 w-8 rounded-xl text-zinc-400 hover:text-zinc-600 hover:bg-zinc-100 cursor-pointer shrink-0"
                  disabled={isTyping}
                  title="Attach file (decorative)"
                >
                  <Paperclip className="w-4 h-4" />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 rounded-xl text-zinc-400 hover:text-zinc-600 hover:bg-zinc-100 cursor-pointer shrink-0"
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
                className="h-8 px-4 bg-[#2E3A2F] text-white hover:bg-[#3E4E3F] transition-all rounded-xl cursor-pointer disabled:opacity-40 shrink-0 flex items-center justify-center gap-1 text-xs font-semibold"
              >
                <span>Send</span>
                <Send className="w-3.5 h-3.5" />
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
