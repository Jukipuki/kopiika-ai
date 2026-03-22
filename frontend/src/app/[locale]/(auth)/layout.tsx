export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-8">
      <div className="w-full max-w-md rounded-2xl border border-foreground/10 bg-background p-8 shadow-lg sm:p-10">
        {children}
      </div>
    </div>
  );
}
