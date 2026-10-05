// NEXT_PUBLIC_ values are inlined at build time, so change them in the
// hosting dashboard and redeploy rather than at runtime.
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

// Empty until the Notion workspace is shared; the nav shows a muted
// label instead of a broken link.
export const NOTION_URL = process.env.NEXT_PUBLIC_NOTION_URL ?? "";
