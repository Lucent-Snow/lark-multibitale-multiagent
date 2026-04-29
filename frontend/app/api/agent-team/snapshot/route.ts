import { runCachedSnapshot } from "../_bridge";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const objectiveId = url.searchParams.get("objectiveId") || "";
  const args = ["snapshot"];
  if (objectiveId) {
    args.push("--objective-id", objectiveId);
  }
  return runCachedSnapshot(args);
}
