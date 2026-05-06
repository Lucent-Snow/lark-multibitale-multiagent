import { handleSnapshot } from "../_bridge";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  return handleSnapshot(request);
}
