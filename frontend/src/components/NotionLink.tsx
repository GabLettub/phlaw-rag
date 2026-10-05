import { NOTION_URL } from "@/lib/config";

// Shows a real link once NEXT_PUBLIC_NOTION_URL is set, otherwise a
// muted label, so the UI never contains a dead link.
export default function NotionLink({ label }: { label: string }) {
  if (!NOTION_URL) {
    return (
      <span
        className="text-slate-400"
        title="Set NEXT_PUBLIC_NOTION_URL to enable this link"
      >
        {label} (link not set)
      </span>
    );
  }
  return (
    <a
      href={NOTION_URL}
      target="_blank"
      rel="noopener noreferrer"
      className="underline"
    >
      {label} ↗
    </a>
  );
}
