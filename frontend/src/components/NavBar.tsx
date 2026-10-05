"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import NotionLink from "./NotionLink";

const LINKS = [
  { href: "/", label: "Chat" },
  { href: "/cases", label: "Cases" },
];

export default function NavBar() {
  const pathname = usePathname();
  return (
    <header className="border-b border-slate-200 dark:border-slate-800">
      <nav className="mx-auto flex max-w-3xl items-center gap-5 px-4 py-3 text-sm">
        <span className="mr-auto font-semibold">PHLaw RAG</span>
        {LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={
              pathname === link.href
                ? "font-semibold underline underline-offset-4"
                : "text-slate-600 hover:underline dark:text-slate-400"
            }
          >
            {link.label}
          </Link>
        ))}
        <NotionLink label="Notion" />
      </nav>
    </header>
  );
}
