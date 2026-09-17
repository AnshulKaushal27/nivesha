"use client";

import { useEffect } from "react";

/**
 * "What is on the screen" — a tiny store each page writes to and the chat dock
 * reads when it sends a message. Keep payloads compact: the backend caps them.
 */
export interface ScreenContext {
  page: string;                 // "rank" | "stock" | "predict" | "arena"
  route: string;
  title: string;
  asOf?: string | null;
  summary: string;              // one or two plain sentences
  data?: Record<string, unknown>;
}

let current: ScreenContext = { page: "unknown", route: "/", title: "AI Investment Arena", summary: "Nothing loaded yet." };
const listeners = new Set<() => void>();

export const getScreen = (): ScreenContext => current;

export function setScreen(next: ScreenContext) {
  current = next;
  listeners.forEach((l) => l());
}

export function subscribeScreen(fn: () => void) {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

/** Publish a screen context whenever `deps` change. Pass null while loading. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function useScreen(ctx: ScreenContext | null, deps: any[]) {
  useEffect(() => { if (ctx) setScreen(ctx); }, deps); // eslint-disable-line react-hooks/exhaustive-deps
}

export const SUGGESTIONS: Record<string, string[]> = {
  rank:    ["Which of these stocks is the calmest?", "Why is the top stock ranked so high?", "What does the Overheat penalty mean?"],
  stock:   ["Why is this stock ranked here?", "What is the biggest weakness in its numbers?", "Any recent news on this company?"],
  predict: ["How much should I trust these odds?", "Which sector looks best right now and why?", "What type of stock is rising lately?"],
  arena:   ["Who is winning and why?", "Which manager is the most cautious?", "Explain the leader's strategy simply."],
  unknown: ["What can you help me with?", "How does Buy Rank work?", "What is the AI Arena?"],
};
