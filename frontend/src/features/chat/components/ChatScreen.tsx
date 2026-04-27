"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { useChatConsent } from "../hooks/useChatConsent";
import { useChatMessages, useChatSession } from "../hooks/useChatSession";
import { useChatStream, type ChatTurnState } from "../hooks/useChatStream";
import { ConsentFirstUseDialog } from "./ConsentFirstUseDialog";
import { ConsentRevokedEmpty } from "./ConsentRevokedEmpty";
// ConsentVersionBumpCard is intentionally not imported here yet — the
// 10.1a consent endpoint exposes only `hasCurrentConsent` (boolean), so
// the FE has no way to detect a version bump. The component is wired and
// exported from the feature folder; ChatScreen will mount it once the
// backend lands a per-user "latest version" delta field.
import { ConversationPane } from "./ConversationPane";
import { Composer } from "./Composer";
import { SessionList } from "./SessionList";

interface ChatScreenProps {
  privacyHref: string;
}

export function ChatScreen({ privacyHref }: ChatScreenProps) {
  const t = useTranslations("chat");
  const consent = useChatConsent();
  const { activeSessionId, sessions, createSession } = useChatSession();
  const sessionId = activeSessionId;
  const stream = useChatStream(sessionId);
  const messagesQuery = useChatMessages(sessionId);

  // Historical transcript rendered before the live stream's turns. The
  // backend filters tool-role rows; the FE just trusts the role union.
  // Live (streaming) turns from useChatStream are appended after; in-flight
  // assistant turns have no DB row yet so they cleanly tail the history.
  const historicalTurns = useMemo<ChatTurnState[]>(() => {
    const pages = messagesQuery.data?.pages ?? [];
    const out: ChatTurnState[] = [];
    for (const page of pages) {
      for (const m of page.messages) {
        if (m.role !== "user" && m.role !== "assistant") continue;
        out.push({
          id: m.id,
          role: m.role,
          text: m.content,
          createdAt: m.createdAt,
        });
      }
    }
    return out;
  }, [messagesQuery.data]);

  const allTurns = useMemo<ChatTurnState[]>(() => {
    const seenIds = new Set(historicalTurns.map((t) => t.id));
    const liveTurns = stream.turns.filter((t) => !seenIds.has(t.id));
    return [...historicalTurns, ...liveTurns];
  }, [historicalTurns, stream.turns]);

  // First-time hint: auto-create a session once consent is in hand and no
  // sessions exist. Avoids a "blank screen with only a New button" first-run.
  // Refs (not state) so the effect doesn't re-render the screen on the flip.
  const autoCreatedRef = useRef(false);
  useEffect(() => {
    if (
      consent.hasCurrentConsent &&
      !consent.isLoading &&
      !autoCreatedRef.current &&
      sessions.length === 0 &&
      !sessionId
    ) {
      autoCreatedRef.current = true;
      void createSession().catch(() => undefined);
    }
  }, [consent.hasCurrentConsent, consent.isLoading, sessions.length, sessionId, createSession]);

  // Drive composer-disabled state from a wall-clock cooldownEndsAt set on
  // the refusal turn (see useChatStream reducer). retryAfterSeconds is a
  // static field — without a tick we'd disable Send forever after the
  // first rate_limited refusal.
  const [now, setNow] = useState(() => Date.now());
  const cooldownActive = useMemo(
    () => stream.turns.some((t) => (t.refusal?.cooldownEndsAt ?? 0) > now),
    [stream.turns, now],
  );
  useEffect(() => {
    if (!cooldownActive) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [cooldownActive]);

  // Loading consent — render nothing intrusive.
  if (consent.isLoading) {
    return <div className="p-8 text-center text-sm text-muted-foreground">{t("loading")}</div>;
  }

  // Post-revoke empty state per AC #9.
  if (consent.consent && consent.consent.hasCurrentConsent === false && consent.consent.grantedAt) {
    // grantedAt non-null while hasCurrentConsent=false ⇒ user revoked previously.
    return <ConsentRevokedEmpty />;
  }

  // First-use modal per AC #9.
  if (!consent.hasCurrentConsent) {
    return (
      <>
        <div className="p-8 text-center text-sm text-muted-foreground">
          {t("consent.first_use.gated_hint")}
        </div>
        <ConsentFirstUseDialog
          open={true}
          onAccept={() => void consent.grant().catch(() => undefined)}
          onDecline={() => undefined}
          privacyHref={privacyHref}
        />
      </>
    );
  }

  // Normal chat surface.
  const lastUserError = [...stream.turns].reverse().find((t) => t.preStreamError != null);
  const errorBanner = lastUserError?.preStreamError ? (
    <div role="alert" className="mb-2 rounded border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">
      {lastUserError.preStreamError.kind === "input_too_long"
        ? t("composer.error_too_long")
        : t("composer.error_generic")}
    </div>
  ) : null;

  return (
    <div className="flex h-[calc(100vh-4rem)] w-full">
      <div className="hidden sm:flex">
        <SessionList />
      </div>
      <div className="flex flex-1 flex-col">
        <ConversationPane turns={allTurns} onRetry={stream.retryLast} />
        <Composer
          onSend={(message) => {
            if (!sessionId) {
              // Pass the freshly-created sessionId straight into send so it
              // doesn't fall back to the stale `null` captured in
              // useChatStream's closure on this render.
              void createSession()
                .then((created) => stream.send(message, created.sessionId))
                .catch(() => undefined);
              return;
            }
            void stream.send(message);
          }}
          disabled={stream.inFlight}
          cooldownActive={cooldownActive}
          errorBanner={errorBanner}
        />
      </div>
    </div>
  );
}

