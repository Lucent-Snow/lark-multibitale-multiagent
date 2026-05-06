const BRIDGE_URL = process.env.BRIDGE_SERVER_URL || "http://127.0.0.1:9800";

type ApiPayload = { ok: boolean; data?: unknown; error?: { code: string; stage: string; message: string; detail?: string; timestamp?: string } };

const snapshotCache = new Map<string, { expiresAt: number; payload: ApiPayload }>();
const inFlightFetches = new Map<string, Promise<ApiPayload>>();

export function getBaseToken(request: Request): string {
  const url = new URL(request.url);
  return url.searchParams.get("baseToken")
    || request.headers.get("x-base-token")
    || process.env.AGENT_TEAM_BASE_TOKEN
    || "";
}

export function withBaseToken(request: Request, args: string[]): string[] {
  const token = getBaseToken(request);
  if (!token) throw new Error("Missing baseToken");
  return [token, ...args];
}

async function fetchBridge(path: string, queryParams: Record<string, string> = {}, timeoutMs = 300_000) {
  const url = new URL(path, BRIDGE_URL);
  for (const [k, v] of Object.entries(queryParams)) {
    if (v) url.searchParams.set(k, v);
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(url.toString(), { signal: controller.signal });
    return (await res.json()) as ApiPayload;
  } catch (err) {
    return {
      ok: false,
      error: {
        code: "BRIDGE_DOWN",
        stage: "bridge",
        message: err instanceof Error ? err.message : "Bridge unreachable",
        detail: `Is bridge_server.py running on ${BRIDGE_URL}?`,
        timestamp: new Date().toISOString(),
      },
    };
  } finally {
    clearTimeout(timer);
  }
}

export async function runBridge(_args: string[], _timeoutMs?: number): Promise<Response> {
  // Legacy — not used by the new bridge
  return Response.json({ ok: false, error: { code: "LEGACY", stage: "bridge", message: "Use bridge server" } }, { status: 500 });
}

export async function runCachedSnapshot(_args: string[]): Promise<Response> {
  // Legacy — not used by the new bridge
  return Response.json({ ok: false, error: { code: "LEGACY", stage: "bridge", message: "Use bridge server" } }, { status: 500 });
}

export function jsonError(code: string, stage: string, message: string, detail = "", status = 500) {
  return Response.json({
    ok: false,
    error: { code, stage, message, detail, timestamp: new Date().toISOString() },
  }, { status });
}

export function requireDashboardWriteAccess(request: Request) {
  const expected = process.env.AGENT_TEAM_DASHBOARD_TOKEN;
  if (!expected && process.env.NODE_ENV !== "production") return null;
  if (!expected) {
    return jsonError("DASHBOARD_TOKEN_REQUIRED", "auth", "Set AGENT_TEAM_DASHBOARD_TOKEN before enabling write actions", "", 503);
  }
  if (request.headers.get("x-agent-team-token") !== expected) {
    return jsonError("UNAUTHORIZED", "auth", "Invalid dashboard operation token", "", 401);
  }
  return null;
}

// ─── Route handlers that use the persistent bridge server ───

export async function handleSnapshot(request: Request): Promise<Response> {
  const token = getBaseToken(request);
  if (!token) return jsonError("NO_TOKEN", "request", "Missing baseToken", "", 400);

  const url = new URL(request.url);
  const objectiveId = url.searchParams.get("objectiveId") || "";

  const cacheKey = `snapshot:${token}:${objectiveId}`;
  const cached = snapshotCache.get(cacheKey);
  if (cached && cached.expiresAt > Date.now()) {
    return Response.json(cached.payload);
  }

  const inflight = inFlightFetches.get(cacheKey);
  if (inflight) {
    const result = await inflight;
    return Response.json(result);
  }

  const promise = fetchBridge("/snapshot", { baseToken: token, objectiveId }).finally(() => {
    inFlightFetches.delete(cacheKey);
  });
  inFlightFetches.set(cacheKey, promise);

  const result = await promise;
  if (result.ok) {
    snapshotCache.set(cacheKey, { expiresAt: Date.now() + 30_000, payload: result });
  }
  return Response.json(result);
}

async function postBridge(path: string, body: Record<string, unknown>, timeoutMs = 300_000) {
  const url = new URL(path, BRIDGE_URL);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url.toString(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    return (await res.json()) as ApiPayload;
  } catch (err) {
    return {
      ok: false,
      error: {
        code: "BRIDGE_DOWN",
        stage: "bridge",
        message: err instanceof Error ? err.message : "Bridge unreachable",
        detail: `Is bridge_server.py running on ${BRIDGE_URL}?`,
        timestamp: new Date().toISOString(),
      },
    };
  } finally {
    clearTimeout(timer);
  }
}

export async function handleCommand(request: Request, path: string): Promise<Response> {
  const token = getBaseToken(request);
  if (!token) return jsonError("NO_TOKEN", "request", "Missing baseToken", "", 400);

  let body: Record<string, unknown> = {};
  try { body = await request.json(); } catch {}

  body.baseToken = token;

  const result = await postBridge(path, body, 300_000);
  return Response.json(result);
}
