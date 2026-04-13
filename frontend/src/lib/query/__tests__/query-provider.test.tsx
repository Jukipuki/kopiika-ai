import { render, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useQuery, useMutation } from "@tanstack/react-query";
import { createUseTranslations } from "@/test-utils/intl-mock";

// Mock next-intl
vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
  useLocale: () => "en",
}));

// Mock next-auth/react
const mockSignOut = vi.fn();
vi.mock("next-auth/react", () => ({
  signOut: (...args: unknown[]) => mockSignOut(...args),
}));

// Mock sonner
const mockToastError = vi.fn();
vi.mock("sonner", () => ({
  toast: {
    error: (...args: unknown[]) => mockToastError(...args),
  },
}));

import QueryProvider from "../query-provider";

function TestQueryComponent({ status }: { status: number }) {
  useQuery({
    queryKey: ["test", status],
    queryFn: async () => {
      throw new Error(`HTTP ${status}`);
    },
    retry: false,
  });

  return <div>test</div>;
}

function TestMutationComponent({
  status,
  autoFire,
}: {
  status: number;
  autoFire?: boolean;
}) {
  const mutation = useMutation({
    mutationFn: async () => {
      throw new Error(`HTTP ${status}`);
    },
  });

  if (autoFire && !mutation.isPending && !mutation.isError) {
    mutation.mutate();
  }

  return <div>mutation</div>;
}

describe("QueryProvider global error handling", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("triggers signOut on 401 error", async () => {
    render(
      <QueryProvider>
        <TestQueryComponent status={401} />
      </QueryProvider>,
    );

    await waitFor(() => {
      expect(mockSignOut).toHaveBeenCalledWith({
        callbackUrl: "/en/login",
      });
    });
  });

  it("shows rate limit toast on 429 error", async () => {
    render(
      <QueryProvider>
        <TestQueryComponent status={429} />
      </QueryProvider>,
    );

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith(
        "Whoa, slow down! Too many requests — please wait a moment.",
      );
    });
  });

  it("shows generic error toast on 500 error", async () => {
    render(
      <QueryProvider>
        <TestQueryComponent status={500} />
      </QueryProvider>,
    );

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith(
        "Oops, something unexpected happened. Please try again.",
      );
    });
  });

  it("does not show toast or signOut for 404 errors", async () => {
    render(
      <QueryProvider>
        <TestQueryComponent status={404} />
      </QueryProvider>,
    );

    // Wait a bit for any async effects
    await new Promise((r) => setTimeout(r, 100));

    expect(mockSignOut).not.toHaveBeenCalled();
    expect(mockToastError).not.toHaveBeenCalled();
  });

  it("triggers signOut on 401 mutation error", async () => {
    render(
      <QueryProvider>
        <TestMutationComponent status={401} autoFire />
      </QueryProvider>,
    );

    await waitFor(() => {
      expect(mockSignOut).toHaveBeenCalledWith({
        callbackUrl: "/en/login",
      });
    });
  });

  it("shows rate limit toast on 429 mutation error", async () => {
    render(
      <QueryProvider>
        <TestMutationComponent status={429} autoFire />
      </QueryProvider>,
    );

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith(
        "Whoa, slow down! Too many requests — please wait a moment.",
      );
    });
  });

  it("shows generic error toast on 500 mutation error", async () => {
    render(
      <QueryProvider>
        <TestMutationComponent status={500} autoFire />
      </QueryProvider>,
    );

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith(
        "Oops, something unexpected happened. Please try again.",
      );
    });
  });
});
