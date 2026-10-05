import ReactMarkdown from "react-markdown";

// The answers use plain markdown (bold, headings, bullets), so a few
// element styles are enough and no typography plugin is needed.
export default function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      components={{
        h3: ({ children }) => (
          <h3 className="mt-4 mb-1 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {children}
          </h3>
        ),
        p: ({ children }) => <p className="my-2 leading-relaxed">{children}</p>,
        ul: ({ children }) => (
          <ul className="my-2 list-disc space-y-1 pl-5">{children}</ul>
        ),
        ol: ({ children }) => (
          <ol className="my-2 list-decimal space-y-1 pl-5">{children}</ol>
        ),
        a: ({ href, children }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="underline"
          >
            {children}
          </a>
        ),
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
