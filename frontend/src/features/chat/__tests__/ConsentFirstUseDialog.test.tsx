import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { createUseTranslations } from "@/test-utils/intl-mock";
import { ConsentFirstUseDialog } from "../components/ConsentFirstUseDialog";

vi.mock("next-intl", () => ({
  useTranslations: createUseTranslations(),
}));

const back = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ back }),
}));

describe("ConsentFirstUseDialog", () => {
  it("renders title, body, and both CTAs", () => {
    render(
      <ConsentFirstUseDialog
        open={true}
        onAccept={vi.fn()}
        onDecline={vi.fn()}
        privacyHref="/en/settings"
      />,
    );
    expect(screen.getByText(/enable chat/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /accept/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /not now/i })).toBeInTheDocument();
  });

  it("Accept calls onAccept", async () => {
    const onAccept = vi.fn();
    const user = userEvent.setup();
    render(
      <ConsentFirstUseDialog
        open={true}
        onAccept={onAccept}
        onDecline={vi.fn()}
        privacyHref="/en/settings"
      />,
    );
    await user.click(screen.getByRole("button", { name: /accept/i }));
    expect(onAccept).toHaveBeenCalled();
  });

  it("Decline calls onDecline + router.back()", async () => {
    const onDecline = vi.fn();
    const user = userEvent.setup();
    render(
      <ConsentFirstUseDialog
        open={true}
        onAccept={vi.fn()}
        onDecline={onDecline}
        privacyHref="/en/settings"
      />,
    );
    await user.click(screen.getByRole("button", { name: /not now/i }));
    expect(onDecline).toHaveBeenCalled();
    expect(back).toHaveBeenCalled();
  });
});
