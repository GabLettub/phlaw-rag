import { API_URL } from "./config";

export type Source = {
  case_id: string;
  title: string;
  gr_no: string;
  section: string;
  snippet: string;
  url: string;
};

export type ChatResult = {
  answer: string;
  intent: "digest" | "follow_up" | "search" | "general" | "out_of_scope";
  case_id: string | null;
  sources: Source[];
};

export type HistoryItem = { role: "user" | "assistant"; content: string };

export type CaseInfo = {
  case_id: string;
  title: string;
  gr_no: string;
  date: string;
  topic: string;
  url: string;
  summary: string;
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

// The backend sends friendly text in `detail` for rate limits (429);
// validation errors send a list, which we replace with a generic line.
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError(
      "Could not reach the server. It may be waking up; try again shortly.",
      0,
    );
  }
  if (!res.ok) {
    let detail = "Something went wrong. Please try again.";
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // keep the generic message
    }
    throw new ApiError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

export function fetchCases(): Promise<CaseInfo[]> {
  return request<CaseInfo[]>("/cases");
}

export function sendChat(
  message: string,
  history: HistoryItem[],
  activeCaseId: string | null,
): Promise<ChatResult> {
  return request<ChatResult>("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      history,
      active_case_id: activeCaseId,
    }),
  });
}
