"use client";

import Link from "next/link";
import { useState } from "react";
import { fmtAgo, fmtInt } from "@/lib/admin/format";
import type { AdminUserRow } from "@/lib/admin/types";
import { Table, Td, Tr } from "./ui";

export function UserSearch({ initial, onSearch }: { initial: string; onSearch: (q: string) => void }) {
  const [q, setQ] = useState(initial);
  return (
    <form
      role="search"
      className="flex max-w-lg gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        onSearch(q.trim());
      }}
    >
      <label htmlFor="admin-user-search" className="sr-only">
        Email or user id
      </label>
      <input
        id="admin-user-search"
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Email or user id"
        maxLength={200}
        className="h-9 min-w-0 flex-1 rounded-full border border-line bg-bg-2 px-4 text-sm text-fg placeholder:text-fg-muted/70 outline-none focus-visible:focus-ring"
      />
      <button type="submit" className="h-9 rounded-full bg-primary px-4 text-sm font-medium text-primary-fg focus-visible:focus-ring">
        Search
      </button>
    </form>
  );
}

export function UsersTable({ users, base = "/admin" }: { users: AdminUserRow[]; base?: string }) {
  return (
    <Table label="Users" head={["Email", "Plan", "Balance", "Joined"]} empty="No users match.">
      {users.map((u) => (
        <Tr key={u.id}>
          <Td className="max-w-72 truncate">
            <Link href={`${base}/users/${u.id}`} className="underline decoration-line underline-offset-4 hover:decoration-fg focus-visible:focus-ring" title={u.id}>
              {u.email || u.id}
            </Link>
          </Td>
          <Td className="capitalize">{u.plan}</Td>
          <Td className={u.balance < 0 ? "text-danger" : undefined}>{fmtInt(u.balance)}</Td>
          <Td className="text-fg-muted" title={u.created_at}>
            {fmtAgo(u.created_at)}
          </Td>
        </Tr>
      ))}
    </Table>
  );
}
