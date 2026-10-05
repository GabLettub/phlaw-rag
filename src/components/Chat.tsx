"use client";

import { useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";

import {
  ApiError,
  type ChatResult,
  type HistoryItem,
  sendChat,
} from "@/lib/api";
import DigestNote from "./DigestNote";
import Markdown from "./Markdown";
import SourcesList from "./SourcesList";

type Message =
  | { role: "user"; content: string }
  | { role: "assistant"; content: string; result?: ChatResult; error?: boolean };

const EXAMPLES = [
  "Digest Knights of Rizal v. DMCI",
  "What is a writ of continuing mandamus?",
  "Do the Rules on Electronic Evidence apply to criminal cases?",
  "Which provisions of the Cybercrime Act were struck down?",
  "Show me environmental law cases",
  "Did the Supreme Court rule on the Eat Bulaga trademark?",
];

// The backend keeps only the last 6 messages, so sending more is waste.
const HISTORY_LIMIT = 6;
// After this long without a reply we assume the free-tier server is
// waking up and say so.
const SLOW_AFTER_MS = 8000;

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [slow, setSlow] = useState(false);
  const [activeCase, setActiveCase] = useState<{
    id: string;
    label: string;
  } | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const autoAsked = useRef(false);
  const searchParams = useSearchParams();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // The cleanup resets the flag, so no state is set in the effect body.
  useEffect(() => {
    if (!loading) return;
    const timer = setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    return () => {
      clearTimeout(timer);
      setSlow(false);
    };
  }, [loading]);

  // The Cases page links here with ?ask=..., which is sent once. The ref
  // stops React's development double-run from sending it twice.
  useEffect(() => {
    const ask = searchParams.get("ask");
    if (ask && !autoAsked.current) {
      autoAsked.current = true;
      window.history.replaceState(null, "", "/");
      void send(ask);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  async function send(text: string) {
    const question = text.trim();
    if (!question || loading) return;
    const history: HistoryItem[] = messages
      .filter((m) => !(m.role === "assistant" && m.error))
      .slice(-HISTORY_LIMIT)
      .map((m) => ({ role: m.role, content: m.content }));
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");
    setLoading(true);
    try {
      const result = await sendChat(question, history, activeCase?.id ?? null);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: result.answer, result },
      ]);
      if (result.case_id) {
        const title =
          result.sources.find((s) => s.case_id === result.case_id)?.title ??
          result.case_id;
        setActiveCase({ id: result.case_id, label: title });
      }
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Something went wrong.";
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: message, error: true },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(input);
  }

  return (
    <div className="flex flex-col gap-4">
      {messages.length === 0 && (
        <section>
          <p className="mb-2 text-sm text-slate-600 dark:text-slate-400">
            Ask about the six indexed decisions. Try one of these:
          </p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => void send(example)}
                className="rounded-full border border-slate-300 px-3 py-1.5 text-left text-sm hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
              >
                {example}
              </button>
            ))}
          </div>
        </section>
      )}

      <div className="flex flex-col gap-4">
        {messages.map((message, index) =>
          message.role === "user" ? (
            <div
              key={index}
              className="self-end max-w-[85%] rounded-2xl bg-slate-900 px-4 py-2 text-white dark:bg-slate-100 dark:text-slate-900"
            >
              {message.content}
            </div>
          ) : (
            <div
              key={index}
              className={`max-w-full rounded-2xl border px-4 py-3 ${
                message.error
                  ? "border-red-300 bg-red-50 text-red-900 dark:border-red-900 dark:bg-red-950 dark:text-red-200"
                  : "border-slate-200 dark:border-slate-700"
              }`}
            >
              {message.error ? (
                <p>{message.content}</p>
              ) : (
                <Markdown>{message.content}</Markdown>
              )}
              {message.result?.intent === "digest" && <DigestNote />}
              {message.result && <SourcesList sources={message.result.sources} />}
            </div>
          ),
        )}
        {loading && (
          <div className="text-sm text-slate-500 dark:text-slate-400">
            Thinking…
            {slow && " The server may be waking up; this can take up to a minute."}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {activeCase && (
        <div className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400">
          <span>
            Follow-up questions are about: <strong>{activeCase.label}</strong>
          </span>
          <button
            type="button"
            onClick={() => setActiveCase(null)}
            className="underline"
          >
            clear
          </button>
        </div>
      )}

      <form onSubmit={onSubmit} className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about a case…"
          maxLength={1000}
          className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-transparent px-3 py-2 dark:border-slate-700"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded-lg bg-slate-900 px-4 py-2 text-white disabled:opacity-40 dark:bg-slate-100 dark:text-slate-900"
        >
          Send
        </button>
      </form>
    </div>
  );
}
