import { jsonError, requireDashboardWriteAccess, runBridge } from "../_bridge";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const authError = requireDashboardWriteAccess(request);
  if (authError) return authError;
  const body = await request.json().catch(() => null);
  if (!body?.title || !body?.description) {
    return jsonError("BAD_REQUEST", "request", "title and description are required", "", 400);
  }
  return runBridge([
    "start-demo",
    "--title", String(body.title),
    "--description", String(body.description),
    "--max-tasks", String(Number.isFinite(Number(body.maxTasks)) ? Number(body.maxTasks) : 4),
    "--workers", String(Number.isFinite(Number(body.workers)) ? Number(body.workers) : 3),
    "--timeout", String(Number.isFinite(Number(body.timeout)) ? Number(body.timeout) : 600),
  ]);
}
