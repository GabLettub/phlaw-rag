import type { Source } from "@/lib/api";

// Sources are what makes an answer checkable, so they are always one
// click away under the answer.
export default function SourcesList({ sources }: { sources: Source[] }) {
  if (sources.length === 0) return null;
  return (
    <details className="mt-3 rounded-lg border border-slate-200 text-sm dark:border-slate-700">
      <summary className="cursor-pointer select-none px-3 py-2 font-medium">
        Sources ({sources.length})
      </summary>
      <ul className="divide-y divide-slate-200 dark:divide-slate-700">
        {sources.map((s, i) => (
          <li key={`${s.case_id}-${i}`} className="px-3 py-2">
            <div className="flex flex-wrap items-center gap-2">
              <a
                href={s.url}
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium underline"
              >
                {s.title}
              </a>
              <span className="text-slate-500 dark:text-slate-400">
                {s.gr_no}
              </span>
              <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">
                {s.section}
              </span>
            </div>
            <p className="mt-1 text-slate-600 dark:text-slate-400">
              {s.snippet}
            </p>
          </li>
        ))}
      </ul>
    </details>
  );
}
