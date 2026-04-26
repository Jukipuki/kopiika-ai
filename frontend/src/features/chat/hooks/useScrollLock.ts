"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// 80-px scroll-lock rule per 10.3a L1605-L1614 + L1659-L1677. While the
// container is within ~80px of the bottom, append-events should auto-scroll;
// once the user scrolls up past that threshold, suppress auto-scroll and
// expose `showJumpButton=true` so a "↓ New messages" anchor can render.

const SCROLL_LOCK_THRESHOLD_PX = 80;

export function useScrollLock<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [showJumpButton, setShowJumpButton] = useState(false);
  const isPinnedRef = useRef(true);

  const isPinned = useCallback(() => {
    const el = ref.current;
    if (!el) return true;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    return distance <= SCROLL_LOCK_THRESHOLD_PX;
  }, []);

  const scrollToBottom = useCallback((smooth = true) => {
    const el = ref.current;
    if (!el) return;
    const reduceMotion =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollTo({ top: el.scrollHeight, behavior: smooth && !reduceMotion ? "smooth" : "auto" });
    isPinnedRef.current = true;
    setShowJumpButton(false);
  }, []);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onScroll = () => {
      const pinned = isPinned();
      isPinnedRef.current = pinned;
      setShowJumpButton(!pinned);
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [isPinned]);

  // Call this whenever new content appended; auto-scroll only if pinned.
  const onContentAppended = useCallback(() => {
    if (isPinnedRef.current) scrollToBottom(false);
    else setShowJumpButton(true);
  }, [scrollToBottom]);

  return { ref, showJumpButton, scrollToBottom, onContentAppended };
}
