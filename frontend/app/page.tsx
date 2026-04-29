"use client";

import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock3,
  Database,
  GitBranch,
  History,
  Loader2,
  MessageSquare,
  Play,
  RefreshCw,
  RotateCcw,
  Send,
  ShieldCheck,
  Users
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import styles from "./page.module.css";

type ApiError = {
  code: string;
  stage: string;
  message: string;
  detail: string;
  timestamp: string;
};

type Worker = {
  id: string;
  name: string;
  role: string;
  status: string;
  capabilities: string;
  current_task_id: string;
  heartbeat_at: string;
  process_id: string;
};

type Task = {
  id: string;
  subject: string;
  description: string;
  role: string;
  status: string;
  owner: string;
  lease_until: string;
  attempt_count: number;
};

type Edge = {
  id: string;
  from_task_id: string;
  to_task_id: string;
  relation: string;
};

type Objective = {
  id: string;
  title: string;
  description: string;
  status: string;
  initiator: string;
  final_result: string;
  created_at: string;
  progress: number;
};

type RecordEnvelope = {
  id: string;
  fields: Record<string, unknown>;
};

type Artifact = {
  artifact_id: string;
  task_id: string;
  author: string;
  title: string;
  content: string;
  created_at: string;
};

type Verification = Record<string, unknown>;

type Snapshot = {
  mode: "real";
  empty: boolean;
  base: { token_suffix: string };
  objective: Objective | null;
  workers: Worker[];
  tasks: Task[];
  edges: Edge[];
  claims: Record<string, unknown>[];
  messages: RecordEnvelope[];
  artifacts: Artifact[];
  verifications: Verification[];
  events: RecordEnvelope[];
  generated_at: string;
};

type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError };

const statusLabels: Record<string, string> = {
  pending: "等待",
  claimed: "已领取",
  in_progress: "工作中",
  completed: "完成",
  failed: "失败",
  idle: "空闲",
  working: "工作中"
};

export default function Home() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>("");
  const [objectiveTitle, setObjectiveTitle] = useState("");
  const [objectiveDescription, setObjectiveDescription] = useState("");
  const [message, setMessage] = useState("");
  const [recipient, setRecipient] = useState("team-lead");
  const [operationToken, setOperationToken] = useState("");
  const loadingSnapshotRef = useRef(false);

  const loadSnapshot = async () => {
    if (loadingSnapshotRef.current) return;
    loadingSnapshotRef.current = true;
    setLoading(true);
    try {
      const response = await fetch("/api/agent-team/snapshot", { cache: "no-store" });
      const payload = (await response.json()) as ApiResult<Snapshot>;
      if (!payload.ok) {
        setError(payload.error);
        setSnapshot(null);
      } else {
        setSnapshot(payload.data);
        setError(null);
        setLastUpdated(new Date().toLocaleTimeString());
      }
    } catch (err) {
      setError({
        code: "CLIENT_FETCH",
        stage: "client",
        message: err instanceof Error ? err.message : "Failed to fetch dashboard snapshot",
        detail: "",
        timestamp: new Date().toISOString()
      });
      setSnapshot(null);
    } finally {
      loadingSnapshotRef.current = false;
      setLoading(false);
    }
  };

  useEffect(() => {
    const tokenLoad = window.setTimeout(() => {
      setOperationToken(window.sessionStorage.getItem("agent-team-operation-token") || "");
    }, 0);
    const initialLoad = window.setTimeout(() => void loadSnapshot(), 0);
    const timer = window.setInterval(() => void loadSnapshot(), 15000);
    return () => {
      window.clearTimeout(tokenLoad);
      window.clearTimeout(initialLoad);
      window.clearInterval(timer);
    };
  }, []);

  const metrics = useMemo(() => buildMetrics(snapshot), [snapshot]);
  const selectedObjective = snapshot?.objective;
  const availableRecipients = useMemo(() => {
    const ids = snapshot?.workers.map((worker) => worker.id) ?? [];
    return ["team-lead", ...ids];
  }, [snapshot]);

  async function submitObjective(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!objectiveTitle.trim() || !objectiveDescription.trim()) return;
    setBusyAction("objective");
    try {
      const result = await postJson("/api/agent-team/objectives", {
        title: objectiveTitle,
        description: objectiveDescription,
        maxTasks: 4
      }, operationToken);
      handleActionResult(result);
      if (result.ok) {
        setObjectiveTitle("");
        setObjectiveDescription("");
        await loadSnapshot();
      }
    } finally {
      setBusyAction(null);
    }
  }

  function updateOperationToken(value: string) {
    setOperationToken(value);
    if (value) {
      window.sessionStorage.setItem("agent-team-operation-token", value);
    } else {
      window.sessionStorage.removeItem("agent-team-operation-token");
    }
  }

  async function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedObjective || !message.trim()) return;
    setBusyAction("message");
    try {
      const result = await postJson("/api/agent-team/messages", {
        objectiveId: selectedObjective.id,
        recipient,
        summary: "Console instruction",
        message
      }, operationToken);
      handleActionResult(result);
      if (result.ok) {
        setMessage("");
        await loadSnapshot();
      }
    } finally {
      setBusyAction(null);
    }
  }

  async function recoverExpired() {
    if (!selectedObjective) return;
    setBusyAction("recover");
    try {
      const result = await postJson("/api/agent-team/recover-expired", {
        objectiveId: selectedObjective.id
      }, operationToken);
      handleActionResult(result);
      await loadSnapshot();
    } finally {
      setBusyAction(null);
    }
  }

  function handleActionResult(result: ApiResult<unknown>) {
    if (!result.ok) {
      setError(result.error);
    }
  }

  return (
    <main className={styles.shell}>
      <header className={styles.header}>
        <div>
          <div className={styles.eyebrow}>
            <Database size={16} />
            Feishu Base Control Plane
          </div>
          <h1>Agent-Team Command Center</h1>
        </div>
        <div className={styles.headerActions}>
          <StatusPill state={error ? "error" : snapshot?.empty ? "empty" : loading && !snapshot ? "loading" : "connected"} />
          <button className={styles.iconButton} onClick={() => void loadSnapshot()} aria-label="刷新">
            {loading ? <Loader2 className={styles.spin} size={18} /> : <RefreshCw size={18} />}
          </button>
        </div>
      </header>

      {error ? <ErrorPanel error={error} /> : null}
      {!error && snapshot?.empty ? <EmptyPanel tokenSuffix={snapshot.base.token_suffix} /> : null}

      <section className={styles.metricsGrid}>
        <Metric icon={<Users size={18} />} label="数字员工" value={metrics.workers} tone="blue" />
        <Metric icon={<Activity size={18} />} label="工作中" value={metrics.working} tone="green" />
        <Metric icon={<GitBranch size={18} />} label="任务" value={metrics.tasks} tone="blue" />
        <Metric icon={<ShieldCheck size={18} />} label="质量验证" value={metrics.verifications} tone="yellow" />
      </section>

      <section className={styles.objectiveBand}>
        <div>
          <span className={styles.sectionLabel}>当前目标</span>
          <h2>{selectedObjective?.title || "未读取到目标记录"}</h2>
          <p>{selectedObjective?.description || "页面只展示真实 Base 数据；如果没有目标记录，这里保持空状态。"}</p>
        </div>
        <div className={styles.progressBox}>
          <span>{Math.round((selectedObjective?.progress ?? 0) * 100)}%</span>
          <div className={styles.progressTrack}>
            <div
              className={styles.progressFill}
              style={{ width: `${Math.round((selectedObjective?.progress ?? 0) * 100)}%` }}
            />
          </div>
          <small>{selectedObjective?.status || "no objective"}</small>
        </div>
      </section>

      <div className={styles.mainGrid}>
        <section className={styles.panel}>
          <PanelTitle icon={<Users size={18} />} title="数字员工" />
          <div className={styles.workerList}>
            {snapshot?.workers.length ? (
              snapshot.workers.map((worker) => <WorkerCard key={worker.id} worker={worker} />)
            ) : (
              <EmptyLine text="真实 Base 中没有 worker 记录。" />
            )}
          </div>
        </section>

        <section className={`${styles.panel} ${styles.taskPanel}`}>
          <PanelTitle icon={<GitBranch size={18} />} title="任务流" />
          <div className={styles.taskFlow}>
            {snapshot?.tasks.length ? (
              snapshot.tasks.map((task) => (
                <TaskRow key={task.id} task={task} edges={snapshot.edges} />
              ))
            ) : (
              <EmptyLine text="真实 Base 中没有 task 记录。" />
            )}
          </div>
        </section>

        <aside className={styles.sideStack}>
          <section className={styles.panel}>
            <PanelTitle icon={<Play size={18} />} title="新目标" />
            <form className={styles.form} onSubmit={submitObjective}>
              <input
                value={objectiveTitle}
                onChange={(event) => setObjectiveTitle(event.target.value)}
                placeholder="输入目标标题"
              />
              <textarea
                value={objectiveDescription}
                onChange={(event) => setObjectiveDescription(event.target.value)}
                placeholder="描述要交给 agent-team 的目标"
                rows={4}
              />
              <button className={styles.primaryButton} disabled={busyAction === "objective"}>
                {busyAction === "objective" ? <Loader2 className={styles.spin} size={16} /> : <Play size={16} />}
                启动目标
              </button>
            </form>
          </section>

          <section className={styles.panel}>
            <PanelTitle icon={<Send size={18} />} title="团队指令" />
            <form className={styles.form} onSubmit={submitMessage}>
              <input
                value={operationToken}
                onChange={(event) => updateOperationToken(event.target.value)}
                placeholder="操作密钥"
                type="password"
                autoComplete="new-password"
              />
              <select value={recipient} onChange={(event) => setRecipient(event.target.value)}>
                {availableRecipients.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
              <textarea
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="写入真实 v2_messages 表"
                rows={4}
              />
              <button className={styles.secondaryButton} disabled={!selectedObjective || busyAction === "message"}>
                {busyAction === "message" ? <Loader2 className={styles.spin} size={16} /> : <MessageSquare size={16} />}
                发送指令
              </button>
            </form>
            <button
              className={styles.ghostButton}
              disabled={!selectedObjective || busyAction === "recover"}
              onClick={() => void recoverExpired()}
            >
              {busyAction === "recover" ? <Loader2 className={styles.spin} size={16} /> : <RotateCcw size={16} />}
              回收过期任务
            </button>
          </section>
        </aside>
      </div>

      <section className={styles.lowerGrid}>
        <section className={styles.panel}>
          <PanelTitle icon={<ShieldCheck size={18} />} title="质量闸门" />
          <VerificationList verifications={snapshot?.verifications ?? []} />
        </section>
        <section className={styles.panel}>
          <PanelTitle icon={<History size={18} />} title="事件流" />
          <EventList events={snapshot?.events ?? []} />
        </section>
        <section className={styles.panel}>
          <PanelTitle icon={<CheckCircle2 size={18} />} title="产物" />
          <ArtifactList artifacts={snapshot?.artifacts ?? []} />
        </section>
      </section>

      <footer className={styles.footer}>
        <span>Base token: {snapshot?.base.token_suffix ? `...${snapshot.base.token_suffix}` : "unavailable"}</span>
        <span>Last refresh: {lastUpdated || "pending"}</span>
      </footer>
    </main>
  );
}

function StatusPill({ state }: { state: "connected" | "error" | "empty" | "loading" }) {
  const label = state === "connected" ? "Connected" : state === "error" ? "Error" : state === "empty" ? "Empty" : "Syncing";
  return <span className={`${styles.statusPill} ${styles[state]}`}>{label}</span>;
}

function ErrorPanel({ error }: { error: ApiError }) {
  return (
    <section className={styles.errorPanel}>
      <AlertTriangle size={22} />
      <div>
        <h2>Control Plane Unavailable</h2>
        <p>{error.message}</p>
        <div className={styles.errorMeta}>
          <code>{error.stage}</code>
          <code>{error.code}</code>
          <code>{new Date(error.timestamp).toLocaleString()}</code>
        </div>
        {error.detail ? <pre>{error.detail}</pre> : null}
      </div>
    </section>
  );
}

function EmptyPanel({ tokenSuffix }: { tokenSuffix: string }) {
  return (
    <section className={styles.emptyPanel}>
      <Database size={22} />
      <div>
        <h2>真实 Base 中暂无 agent-team 数据</h2>
        <p>控制台已连接 Base ...{tokenSuffix}，但没有读取到 objective 记录。</p>
      </div>
    </section>
  );
}

function Metric({ icon, label, value, tone }: {
  icon: ReactNode;
  label: string;
  value: number;
  tone: "blue" | "green" | "yellow";
}) {
  return (
    <div className={`${styles.metric} ${styles[tone]}`}>
      <div className={styles.metricIcon}>{icon}</div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  );
}

function PanelTitle({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <div className={styles.panelTitle}>
      {icon}
      <h3>{title}</h3>
    </div>
  );
}

function WorkerCard({ worker }: { worker: Worker }) {
  const stale = isStale(worker.heartbeat_at);
  return (
    <article className={styles.workerCard}>
      <div className={styles.avatar}>{worker.role.slice(0, 2).toUpperCase()}</div>
      <div className={styles.workerBody}>
        <div className={styles.workerTop}>
          <strong>{worker.id}</strong>
          <StatusDot status={stale ? "stale" : worker.status} />
        </div>
        <span>{worker.role}</span>
        <small>{worker.current_task_id || "无当前任务"}</small>
      </div>
    </article>
  );
}

function TaskRow({ task, edges }: { task: Task; edges: Edge[] }) {
  const blockers = edges.filter((edge) => edge.to_task_id === task.id);
  return (
    <article className={`${styles.taskRow} ${styles[`task_${task.status}`] || ""}`}>
      <div className={styles.taskState}>
        <StatusDot status={task.status} />
        <span>{statusLabels[task.status] || task.status}</span>
      </div>
      <div className={styles.taskMain}>
        <h4>{task.subject}</h4>
        <p>{task.description}</p>
        <div className={styles.taskMeta}>
          <span>{task.role}</span>
          <span>{task.owner || "unassigned"}</span>
          <span>attempt {task.attempt_count}</span>
          {blockers.length ? <span>{blockers.length} blockers</span> : null}
        </div>
      </div>
      <ArrowRight size={18} className={styles.taskArrow} />
    </article>
  );
}

function VerificationList({ verifications }: { verifications: Verification[] }) {
  if (!verifications.length) return <EmptyLine text="暂无 verification 记录。" />;
  return (
    <div className={styles.compactList}>
      {verifications.slice(-6).reverse().map((item, index) => {
        const verdict = String(item["结论"] || item.verdict || "UNKNOWN");
        return (
          <div key={`${String(item.verification_id || index)}`} className={styles.compactItem}>
            <StatusDot status={verdict === "PASS" ? "completed" : "failed"} />
            <div>
              <strong>{verdict}</strong>
              <span>{String(item.task_id || item["关联任务ID"] || "")}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function EventList({ events }: { events: RecordEnvelope[] }) {
  if (!events.length) return <EmptyLine text="暂无 event 记录。" />;
  return (
    <div className={styles.timeline}>
      {events.slice(-8).reverse().map((event) => (
        <div key={event.id} className={styles.timelineItem}>
          <Clock3 size={14} />
          <div>
            <strong>{String(event.fields.event_type || "")}</strong>
              <span>{String(event.fields.actor || "")} {"->"} {String(event.fields.target_id || "")}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function ArtifactList({ artifacts }: { artifacts: Artifact[] }) {
  if (!artifacts.length) return <EmptyLine text="暂无 artifact 记录。" />;
  return (
    <div className={styles.artifactList}>
      {artifacts.slice(-4).reverse().map((artifact) => (
        <article key={artifact.artifact_id} className={styles.artifactItem}>
          <strong>{artifact.title || artifact.artifact_id}</strong>
          <span>{artifact.author} / {artifact.task_id}</span>
          <p>{artifact.content}</p>
        </article>
      ))}
    </div>
  );
}

function StatusDot({ status }: { status: string }) {
  return <span className={`${styles.dot} ${styles[`dot_${status}`] || styles.dot_pending}`} />;
}

function EmptyLine({ text }: { text: string }) {
  return <div className={styles.emptyLine}>{text}</div>;
}

async function postJson(url: string, body: Record<string, unknown>, token: string): Promise<ApiResult<unknown>> {
  try {
    const response = await fetch(url, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(token ? { "x-agent-team-token": token } : {})
    },
    body: JSON.stringify(body)
  });
    return response.json() as Promise<ApiResult<unknown>>;
  } catch (err) {
    return {
      ok: false,
      error: {
        code: "CLIENT_ACTION",
        stage: "client",
        message: err instanceof Error ? err.message : "Action request failed",
        detail: "",
        timestamp: new Date().toISOString()
      }
    };
  }
}

function buildMetrics(snapshot: Snapshot | null) {
  const workers = snapshot?.workers.length ?? 0;
  const working = snapshot?.workers.filter((worker) => worker.status === "working").length ?? 0;
  const tasks = snapshot?.tasks.length ?? 0;
  const verifications = snapshot?.verifications.length ?? 0;
  return { workers, working, tasks, verifications };
}

function isStale(value: string) {
  if (!value) return false;
  const time = Date.parse(value);
  if (Number.isNaN(time)) return false;
  return Date.now() - time > 5 * 60 * 1000;
}
