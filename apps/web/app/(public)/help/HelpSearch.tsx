"use client";
import Link from "next/link";
import { useState } from "react";
import { filterHelp, type HelpSearchEntry } from "@/lib/help";

export function HelpSearch({ entries }: { entries: HelpSearchEntry[] }) {
  const [query, setQuery] = useState("");
  const results = filterHelp(entries, query);
  return (
    <section aria-label="Help articles" className="mt-10">
      <label htmlFor="help-search" className="mb-2 block text-sm font-medium">Search the help center</label>
      <input id="help-search" type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Try Blender, credits or textures" className="h-12 w-full rounded-md border border-line bg-bg-1 px-4 text-base text-fg placeholder:text-fg-muted focus-visible:focus-ring" />
      <p role="status" className="my-4 text-sm text-fg-muted">{results.length} {results.length === 1 ? "article" : "articles"}{query.trim() ? " found" : " to help you get started"}</p>
      {results.length ? (
        <ul className="grid gap-3 sm:grid-cols-2">
          {results.map((article) => (
            <li key={article.slug}>
              <Link href={`/help/${article.slug}`} className="flex h-full flex-col rounded-lg border border-line bg-bg-1 p-5 transition-colors hover:bg-bg-2 focus-visible:focus-ring">
                <h2 className="text-base font-medium">{article.title}<span aria-hidden className="ml-2 text-fg-muted">↗</span></h2>
                <p className="mt-2 text-sm leading-relaxed text-fg-muted">{article.summary}</p>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <div className="rounded-lg border border-line p-6">
          <h2 className="font-medium">No matching articles</h2>
          <p className="mt-2 text-sm text-fg-muted">Try a shorter search, such as “upload” or “credits”.</p>
          <button type="button" onClick={() => setQuery("")} className="mt-4 rounded-sm text-sm underline underline-offset-4 focus-visible:focus-ring">Clear search</button>
        </div>
      )}
    </section>
  );
}
