import { jsonError, requireDashboardWriteAccess, runBridge } from "../_bridge";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const authError = requireDashboardWriteAccess(request);
  if (authError) return authError;
  const body = await request.json().catch(() => null);
  if (!body?.objectiveId || !body?.recipient || !body?.summary || !body?.message) {
    return jsonError("BAD_REQUEST", "request", "objectiveId, recipient, summary and message are required", "", 400);
  }

  return runBridge([
    "send-message",
    "--objective-id",
    String(body.objectiveId),
    "--sender",
    String(body.sender || "console"),
    "--recipient",
    String(body.recipient),
    "--summary",
    String(body.summary),
    "--message",
    String(body.message),
    "--task-id",
    String(body.taskId || "")
  ]);
}
