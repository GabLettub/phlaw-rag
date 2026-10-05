import NotionLink from "./NotionLink";

const STEPS = [
  {
    title: "Queue",
    text: "An admin adds a row to the Notion Case Queue with Status = Queued.",
  },
  {
    title: "Index",
    text: "n8n sees the row, sets Processing, and calls /ingest. The decision is chunked and stored in Pinecone, then the row becomes Indexed (or Failed with the error).",
  },
  {
    title: "Digest",
    text: "n8n calls /digest and creates a page in Notion Case Digests with Facts, Issues, Ruling and Doctrine.",
  },
  {
    title: "Ask",
    text: "The case is now searchable here. Ask for a digest in the chat, or open the saved one in Notion.",
  },
];

// Describes the admin-only n8n pipeline. Adding cases is deliberately
// not public, so this panel explains the flow instead of offering a
// button.
export default function AutomationPanel() {
  return (
    <details className="rounded-lg border border-slate-200 text-sm dark:border-slate-700">
      <summary className="cursor-pointer select-none px-3 py-2 font-medium">
        How digests get into Notion (n8n automation)
      </summary>
      <div className="space-y-3 px-3 pb-3">
        <ol className="space-y-2">
          {STEPS.map((step, i) => (
            <li key={step.title} className="flex gap-3">
              <span className="mt-0.5 flex h-5 w-5 flex-none items-center justify-center rounded-full bg-slate-200 text-xs font-semibold dark:bg-slate-700">
                {i + 1}
              </span>
              <p>
                <span className="font-medium">{step.title}.</span>{" "}
                <span className="text-slate-600 dark:text-slate-400">
                  {step.text}
                </span>
              </p>
            </li>
          ))}
        </ol>
        <p className="text-slate-500 dark:text-slate-400">
          Adding cases is admin-only, so there is no public save button. See
          the queue and the saved digests in <NotionLink label="Notion" />.
        </p>
      </div>
    </details>
  );
}
