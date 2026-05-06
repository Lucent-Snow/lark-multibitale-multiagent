import { jsonError, requireDashboardWriteAccess, runBridge, withBaseToken } from "../_bridge";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const authError = requireDashboardWriteAccess(request);
  if (authError) return authError;
  const body = await request.json().catch(() => null);
  if (!body?.tableName || !body?.fieldName) {
    return jsonError("BAD_REQUEST", "request", "tableName and fieldName are required", "", 400);
  }
  return runBridge(withBaseToken(request, [
    "add-field",
    "--table-name", String(body.tableName),
    "--field-name", String(body.fieldName),
  ]));
}
