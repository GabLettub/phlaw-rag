"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiError, type CaseInfo, fetchCases } from "@/lib/api";

export default function CasesPage() {
  const [cases, setCases] = useState<CaseInfo[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchCases()
      .then(setCases)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Could not load cases."),
      );
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold">Indexed cases</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          The six Supreme Court decisions the chatbot can answer from.
        </p>
      </div>

      {error && <p className="text-red-700 dark:text-red-300">{error}</p>}
      {!cases && !error && (
        <p className="text-sm text-slate-500">
          Loading… the server may be waking up.
        </p>
      )}

      <ul className="flex flex-col gap-3">
        {cases?.map((c) => (
          <li
            key={c.case_id}
            className="rounded-lg border border-slate-200 p-4 dark:border-slate-700"
          >
            <h2 className="font-semibold">{c.title}</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {c.gr_no} · {c.date} · {c.topic}
            </p>
            <p className="mt-2 text-sm leading-relaxed">{c.summary}</p>
            <div className="mt-3 flex gap-4 text-sm">
              <Link
                href={`/?ask=${encodeURIComponent(`Digest ${c.title}`)}`}
                className="font-medium underline"
              >
                Ask for a digest
              </Link>
              <a
                href={c.url}
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
              >
                Read the decision ↗
              </a>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
