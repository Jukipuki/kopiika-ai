"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import LoginForm from "@/features/auth/components/LoginForm";

function LoginContent() {
  const params = useParams();
  const locale = (params?.locale as string) || "en";

  return (
    <>
      <h1 className="text-2xl font-semibold text-foreground text-center mb-6">
        Sign in to your account
      </h1>

      <LoginForm />

      <p className="mt-6 text-center text-sm text-foreground/60">
        Don&apos;t have an account?{" "}
        <Link href={`/${locale}/signup`} className="text-[#6C63FF] hover:underline">
          Sign up
        </Link>
      </p>
    </>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[200px] items-center justify-center">
          <div className="text-foreground/50 text-sm">Loading...</div>
        </div>
      }
    >
      <LoginContent />
    </Suspense>
  );
}
