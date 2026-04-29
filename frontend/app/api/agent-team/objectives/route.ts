import { jsonError, requireDashboardWriteAccess, runBridge } from "../_bridge";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const authError = requireDashboardWriteAccess(request);
  if (authError) return authError;
  const body = await request.json().catch(() => null);
  if (!body?.title || !body?.description) {
    return jsonError("BAD_REQUEST", "request", "title and description are required", "", 400);
  }
  const maxTasks = Number.isFinite(Number(body.maxTasks)) ? String(Number(body.maxTasks)) : "4";

  return runBridge([
    "start-objective",
    "--title",
    String(body.title),
    "--description",
    String(body.description),
    "--max-tasks",
    maxTasks
  ]);
}
