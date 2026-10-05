import NotionLink from "./NotionLink";

// Shown under digest answers so the chat makes the n8n pipeline visible.
export default function DigestNote() {
  return (
    <p className="mt-3 rounded-lg bg-slate-100 px-3 py-2 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
      This digest was generated live for the chat. Saved digests are
      published to Notion by the n8n pipeline: <NotionLink label="open Notion" />
      .
    </p>
  );
}
