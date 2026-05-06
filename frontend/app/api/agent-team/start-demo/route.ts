import { handleCommand, requireDashboardWriteAccess } from "../_bridge";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const authError = requireDashboardWriteAccess(request);
  if (authError) return authError;
  return handleCommand(request, "/start-demo");
}
