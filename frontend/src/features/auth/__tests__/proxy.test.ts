import { describe, it, expect, vi, beforeEach } from "vitest";

// Use vi.hoisted so these are available inside vi.mock factories
const { holder, tracking } = vi.hoisted(() => ({
  holder: { handler: null as Function | null },
  tracking: { redirectCalls: [] as URL[], nextCalls: 0, intlCalls: 0 },
}));

// Mock next-auth config — capture the handler passed to auth()
vi.mock("@/lib/auth/next-auth-config", () => ({
  auth: (handler: Function) => {
    holder.handler = handler;
    return handler;
  },
}));

vi.mock("next/server", () => ({
  NextResponse: {
    redirect: (url: URL) => {
      tracking.redirectCalls.push(url);
      return { type: "redirect", url: url.toString() };
    },
    next: () => {
      tracking.nextCalls++;
      return { type: "next" };
    },
  },
}));

// Mock next-intl/middleware — createIntlMiddleware returns a function that tracks calls
vi.mock("next-intl/middleware", () => ({
  default: () => (req: unknown) => {
    tracking.intlCalls++;
    return { type: "intl", req };
  },
}));

// Mock i18n routing config
vi.mock("@/i18n/routing", () => ({
  routing: {
    locales: ["uk", "en"],
    defaultLocale: "uk",
  },
}));

// Force proxy.ts to load (triggers auth() mock which captures handler)
import "@/proxy";

function createMockRequest(pathname: string, auth: any = null) {
  return {
    nextUrl: { pathname },
    url: "http://localhost:3000" + pathname,
    auth,
  };
}

describe("proxy.ts", () => {
  beforeEach(() => {
    tracking.redirectCalls = [];
    tracking.nextCalls = 0;
    tracking.intlCalls = 0;
  });

  it("7.4 redirects unauthenticated requests to dashboard routes → login page", () => {
    const req = createMockRequest("/en/dashboard", null);
    holder.handler!(req);

    expect(tracking.redirectCalls).toHaveLength(1);
    expect(tracking.redirectCalls[0].toString()).toContain("/en/login");
    expect(tracking.redirectCalls[0].toString()).toContain(
      `callbackUrl=${encodeURIComponent("/en/dashboard")}`
    );
  });

  it("7.4b redirects with correct locale prefix", () => {
    const req = createMockRequest("/uk/settings/profile", null);
    holder.handler!(req);

    expect(tracking.redirectCalls).toHaveLength(1);
    expect(tracking.redirectCalls[0].toString()).toContain("/uk/login");
  });

  it("7.5 allows unauthenticated access to login page", () => {
    const req = createMockRequest("/en/login", null);
    holder.handler!(req);

    expect(tracking.redirectCalls).toHaveLength(0);
    expect(tracking.intlCalls).toBe(1);
  });

  it("7.5b allows unauthenticated access to signup page", () => {
    const req = createMockRequest("/en/signup", null);
    holder.handler!(req);

    expect(tracking.redirectCalls).toHaveLength(0);
    expect(tracking.intlCalls).toBe(1);
  });

  it("7.5c allows unauthenticated access to API auth routes", () => {
    const req = createMockRequest("/api/auth/callback/credentials", null);
    holder.handler!(req);

    expect(tracking.redirectCalls).toHaveLength(0);
    // API auth routes bypass i18n and call NextResponse.next() directly
    expect(tracking.nextCalls).toBe(1);
  });

  it("allows authenticated users to access dashboard routes", () => {
    const req = createMockRequest("/en/dashboard", {
      user: { email: "test@example.com" },
    });
    holder.handler!(req);

    expect(tracking.redirectCalls).toHaveLength(0);
    expect(tracking.intlCalls).toBe(1);
  });
});
