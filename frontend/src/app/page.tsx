"use client";

import { useEffect, useState } from "react";

interface HealthResponse {
  status: string;
  version: string;
}

export default function Home() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    fetch(`${apiUrl}/health`)
      .then((res) => res.json())
      .then((data: HealthResponse) => setHealth(data))
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <div className="flex flex-col flex-1 items-center justify-center font-sans">
      <main className="flex flex-col items-center gap-8 p-16">
        <h1 className="text-4xl font-semibold tracking-tight">Kopiika AI</h1>
        <p className="text-lg text-zinc-600 dark:text-zinc-400">
          AI-powered personal finance education
        </p>

        <div className="mt-8 rounded-lg border border-zinc-200 p-6 dark:border-zinc-800">
          <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-zinc-500">
            Backend Health
          </h2>
          {health ? (
            <div className="space-y-2">
              <p className="text-green-600">
                Status: {health.status}
              </p>
              <p className="text-zinc-600 dark:text-zinc-400">
                Version: {health.version}
              </p>
            </div>
          ) : error ? (
            <p className="text-red-500">
              Error: {error}
            </p>
          ) : (
            <p className="text-zinc-400">Connecting...</p>
          )}
        </div>
      </main>
    </div>
  );
}
