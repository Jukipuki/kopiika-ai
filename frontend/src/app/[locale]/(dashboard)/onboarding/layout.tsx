/**
 * Minimal onboarding layout — intentionally overrides the parent
 * ``(dashboard)/layout.tsx`` dashboard chrome (header nav, upload FAB)
 * so users who have not yet granted consent see a clean screen.
 *
 * Auth is already enforced by the parent ``(dashboard)/layout.tsx``
 * ``AuthGuard``. ``ConsentGuard`` is NOT applied here — the parent layout's
 * ``ConsentGuard`` short-circuits on ``/onboarding`` routes to avoid an
 * infinite redirect loop.
 */
export default function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-background">
      <main>{children}</main>
    </div>
  );
}
