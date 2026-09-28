import { authEntry } from "@/lib/server/authEntry";

export async function POST(request: Request) {
  return authEntry(request, "forgot-password");
}
