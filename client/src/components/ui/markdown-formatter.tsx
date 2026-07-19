import React from "react";

export function parseInlineMarkdown(text: string): React.ReactNode[] {
  const tokens: React.ReactNode[] = [];
  
  // Regex to match bold (**text** or __text__) and italic (*text* or _text_)
  const regex = /(\*\*.*?\*\*|\*.*?\*|__.*?__|__.*?__)/g;
  const parts = text.split(regex);
  
  parts.forEach((part, index) => {
    if (!part) return;
    
    if (part.startsWith("**") && part.endsWith("**")) {
      const inner = part.slice(2, -2);
      tokens.push(
        <strong key={index} className="font-bold text-zinc-900">
          {parseInlineProductHighlight(inner, index)}
        </strong>
      );
    } else if (part.startsWith("__") && part.endsWith("__")) {
      const inner = part.slice(2, -2);
      tokens.push(
        <strong key={index} className="font-bold text-zinc-900">
          {parseInlineProductHighlight(inner, index)}
        </strong>
      );
    } else if (part.startsWith("*") && part.endsWith("*")) {
      const inner = part.slice(1, -1);
      tokens.push(<em key={index} className="italic text-zinc-800">{inner}</em>);
    } else if (part.startsWith("_") && part.endsWith("_")) {
      const inner = part.slice(1, -1);
      tokens.push(<em key={index} className="italic text-zinc-800">{inner}</em>);
    } else {
      tokens.push(...parseInlineProductHighlight(part, index));
    }
  });
  
  return tokens;
}

function parseInlineProductHighlight(text: string, baseIndex: number): React.ReactNode[] {
  const products = [
    "MaxaPro-DS Dairy",
    "MaxaPro Liquid",
    "Buffalo-Power 2X",
    "Buffalo-F 1.5X",
    "Horsa-550X-Turbo",
    "TrioSan Gold"
  ];
  
  const prodRegex = new RegExp(`(${products.join("|")})`, "g");
  const parts = text.split(prodRegex);
  const segments: React.ReactNode[] = [];
  
  parts.forEach((part, pIdx) => {
    if (products.includes(part)) {
      segments.push(
        <span 
          key={`${baseIndex}-prod-${pIdx}`} 
          className="text-[#2E3A2F] font-bold bg-[#E8F0E9] px-1.5 py-0.5 rounded border border-[#2E3A2F]/10 shadow-3xs"
        >
          {part}
        </span>
      );
    } else {
      segments.push(part);
    }
  });
  
  return segments;
}

interface MarkdownFormatterProps {
  content: string;
}

export function MarkdownFormatter({ content }: MarkdownFormatterProps) {
  if (!content) return null;
  
  // Normalization: split by lines
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  
  let currentList: { type: "ol" | "ul"; items: React.ReactNode[] } | null = null;
  
  const flushList = (key: number) => {
    if (currentList) {
      if (currentList.type === "ol") {
        elements.push(
          <ol key={`list-${key}`} className="list-decimal pl-6 my-2 space-y-1.5 text-zinc-800">
            {currentList.items}
          </ol>
        );
      } else {
        elements.push(
          <ul key={`list-${key}`} className="list-disc pl-6 my-2 space-y-1.5 text-zinc-800">
            {currentList.items}
          </ul>
        );
      }
      currentList = null;
    }
  };
  
  lines.forEach((line, idx) => {
    const trimmed = line.trim();
    
    // 1. Headers Match (e.g. ## Header)
    const headerMatch = trimmed.match(/^(#{1,3})\s+(.*)$/);
    // 2. Numbered List Match (e.g. 1. Item)
    const numListMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);
    // 3. Bullet List Match (e.g. - Item or * Item)
    const bulletListMatch = trimmed.match(/^([-\*])\s+(.*)$/);
    
    if (headerMatch) {
      flushList(idx);
      const level = headerMatch[1].length;
      const textContent = headerMatch[2];
      if (level === 1) {
        elements.push(
          <h1 key={`h1-${idx}`} className="text-base font-bold text-zinc-950 mt-4 mb-2">
            {parseInlineMarkdown(textContent)}
          </h1>
        );
      } else if (level === 2) {
        elements.push(
          <h2 key={`h2-${idx}`} className="text-sm font-bold text-zinc-900 mt-3 mb-1.5">
            {parseInlineMarkdown(textContent)}
          </h2>
        );
      } else {
        elements.push(
          <h3 key={`h3-${idx}`} className="text-xs font-bold text-zinc-800 mt-2.5 mb-1">
            {parseInlineMarkdown(textContent)}
          </h3>
        );
      }
    } else if (numListMatch) {
      const content = numListMatch[2];
      const itemNode = (
        <li key={`li-${idx}`} className="leading-relaxed">
          {parseInlineMarkdown(content)}
        </li>
      );
      
      if (currentList && currentList.type === "ol") {
        currentList.items.push(itemNode);
      } else {
        flushList(idx);
        currentList = { type: "ol", items: [itemNode] };
      }
    } else if (bulletListMatch) {
      const content = bulletListMatch[2];
      const itemNode = (
        <li key={`li-${idx}`} className="leading-relaxed">
          {parseInlineMarkdown(content)}
        </li>
      );
      
      if (currentList && currentList.type === "ul") {
        currentList.items.push(itemNode);
      } else {
        flushList(idx);
        currentList = { type: "ul", items: [itemNode] };
      }
    } else {
      // Standard Text or Empty Line
      flushList(idx);
      if (trimmed) {
        elements.push(
          <p key={`p-${idx}`} className="my-2.5 leading-relaxed text-zinc-800">
            {parseInlineMarkdown(trimmed)}
          </p>
        );
      }
    }
  });
  
  flushList(lines.length);
  
  return <div className="text-[13px] text-zinc-800 leading-relaxed font-normal">{elements}</div>;
}
