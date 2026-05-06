import { jsonError, requireDashboardWriteAccess, runBridge, withBaseToken } from "../_bridge";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const authError = requireDashboardWriteAccess(request);
  if (authError) return authError;
  const body = await request.json().catch(() => null);
  if (!body?.name) {
    return jsonError("BAD_REQUEST", "request", "name is required", "", 400);
  }
  return runBridge(withBaseToken(request, [
    "delete-table",
    "--name", String(body.name),
  ]));
}
