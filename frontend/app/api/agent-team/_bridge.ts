import { spawn } from "node:child_process";
import path from "node:path";

export type BridgeError = {
  code: string;
  stage: string;
  message: string;
  detail: string;
  timestamp: string;
};

const repoRoot = path.resolve(process.cwd(), "..");
const snapshotCache = new Map<string, { expiresAt: number; payload: unknown; status: number }>();
const inFlightSnapshots = new Map<string, Promise<{ payload: unknown; status: number }>>();

export async function runBridge(args: string[]) {
  const result = await runBridgeResult(args);
  return Response.json(result.payload, { status: result.status });
}

export async function runCachedSnapshot(args: string[]) {
  const key = args.join("\u001f");
  const cached = snapshotCache.get(key);
  if (cached && cached.expiresAt > Date.now()) {
    return Response.json(cached.payload, { status: cached.status });
  }
  const existing = inFlightSnapshots.get(key);
  if (existing) {
    const result = await existing;
    return Response.json(result.payload, { status: result.status });
  }
  const pending = runBridgeResult(args).finally(() => {
    inFlightSnapshots.delete(key);
  });
  inFlightSnapshots.set(key, pending);
  const result = await pending;
  if (result.status === 200) {
    snapshotCache.set(key, {
      ...result,
      expiresAt: Date.now() + 5000
    });
  }
  return Response.json(result.payload, { status: result.status });
}

export function requireDashboardWriteAccess(request: Request) {
  const expected = process.env.AGENT_TEAM_DASHBOARD_TOKEN;
  if (!expected && process.env.NODE_ENV !== "production") return null;
  if (!expected) {
    return jsonError(
      "DASHBOARD_TOKEN_REQUIRED",
      "auth",
      "Set AGENT_TEAM_DASHBOARD_TOKEN before enabling write actions",
      "",
      503
    );
  }
  if (request.headers.get("x-agent-team-token") !== expected) {
    return jsonError("UNAUTHORIZED", "auth", "Invalid dashboard operation token", "", 401);
  }
  return null;
}

async function runBridgeResult(args: string[]) {
  return new Promise<{ payload: unknown; status: number }>((resolve) => {
    const child = spawn("python", ["-m", "src.agent_team_v2.dashboard_bridge", ...args], {
      cwd: repoRoot,
      env: {
        ...process.env,
        PYTHONIOENCODING: "utf-8"
      },
      windowsHide: true
    });

    let stdout = "";
    let stderr = "";
    const timeout = setTimeout(() => {
      child.kill();
      resolve(errorPayload("BRIDGE_TIMEOUT", "bridge_timeout", "Python bridge timed out", safeDetail(stderr), 504));
    }, 120000);

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      clearTimeout(timeout);
      resolve(errorPayload("BRIDGE_SPAWN", "bridge_spawn", error.message, safeDetail(stderr), 500));
    });
    child.on("close", () => {
      clearTimeout(timeout);
      const raw = stdout.trim();
      if (!raw) {
        resolve(errorPayload("BRIDGE_EMPTY", "bridge", "Python bridge returned no output", safeDetail(stderr), 502));
        return;
      }
      try {
        const parsed = JSON.parse(raw);
        const status = parsed.ok === false ? 502 : 200;
        resolve({ payload: parsed, status });
      } catch {
        resolve(errorPayload("BRIDGE_PARSE", "bridge_parse", "Bridge returned invalid JSON", safeDetail(stderr), 502));
      }
    });
  });
}

export function jsonError(code: string, stage: string, message: string, detail = "", status = 500) {
  return Response.json(errorPayload(code, stage, message, detail, status).payload, { status });
}

function errorPayload(code: string, stage: string, message: string, detail = "", status = 500) {
  return {
    payload: {
      ok: false,
      error: {
        code,
        stage,
        message,
        detail,
        timestamp: new Date().toISOString()
      }
    },
    status
  };
}

function safeDetail(value: string) {
  const cleaned = value.trim();
  if (!cleaned) return "";
  return cleaned.split(/\r?\n/).slice(-3).join("\n").slice(0, 600);
}
