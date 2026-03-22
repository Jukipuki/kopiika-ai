"use client";

import { useState, useEffect, useCallback, useRef } from "react";

interface UseIdleTimeoutOptions {
  timeoutMs: number;
  onTimeout?: () => void;
}

export function useIdleTimeout({ timeoutMs, onTimeout }: UseIdleTimeoutOptions) {
  const [isTimedOut, setIsTimedOut] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onTimeoutRef = useRef(onTimeout);

  useEffect(() => {
    onTimeoutRef.current = onTimeout;
  }, [onTimeout]);

  const resetTimeout = useCallback(() => {
    setIsTimedOut(false);
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    timerRef.current = setTimeout(() => {
      setIsTimedOut(true);
      onTimeoutRef.current?.();
    }, timeoutMs);
  }, [timeoutMs]);

  useEffect(() => {
    const events = ["mousemove", "keydown", "touchstart", "scroll", "click"];

    const handleActivity = () => {
      if (!isTimedOut) {
        // Reset timer without calling setState — just restart the timer
        if (timerRef.current) {
          clearTimeout(timerRef.current);
        }
        timerRef.current = setTimeout(() => {
          setIsTimedOut(true);
          onTimeoutRef.current?.();
        }, timeoutMs);
      }
    };

    // Start the initial timer directly (no setState needed — already false)
    timerRef.current = setTimeout(() => {
      setIsTimedOut(true);
      onTimeoutRef.current?.();
    }, timeoutMs);

    events.forEach((event) => {
      window.addEventListener(event, handleActivity, { passive: true });
    });

    return () => {
      events.forEach((event) => {
        window.removeEventListener(event, handleActivity);
      });
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [timeoutMs, isTimedOut]);

  return { isTimedOut, resetTimeout };
}
