import { jsonError, requireDashboardWriteAccess, runBridge } from "../_bridge";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const authError = requireDashboardWriteAccess(request);
  if (authError) return authError;
  const body = await request.json().catch(() => null);
  if (!body?.objectiveId) {
    return jsonError("BAD_REQUEST", "request", "objectiveId is required", "", 400);
  }

  return runBridge(["recover-expired", "--objective-id", String(body.objectiveId)]);
}
