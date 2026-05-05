"use client";

import {
  Activity, AlertTriangle, ArrowRight, BarChart3, CheckCircle2, ChevronDown, ChevronRight,
  Clock3, Cpu, Eye, EyeOff, FileText, GitBranch, HelpCircle,
  Loader2, MessageSquare, Play, RefreshCw, RotateCcw,
  Send, ShieldCheck, Sparkles, Terminal, Users, X, Zap,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import styles from "./page.module.css";
import { SCENARIOS, Scenario } from "./scenarios";

/* ===== Types ===== */
type ApiError = {
  code: string; stage: string; message: string;
  detail: string; timestamp: string;
};

type Worker = {
  id: string; name: string; role: string; status: string;
  capabilities: string; current_task_id: string;
  heartbeat_at: string; process_id: string;
};

type Task = {
  id: string; subject: string; description: string;
  role: string; status: string; owner: string;
  lease_until: string; attempt_count: number;
};

type Edge = {
  id: string; from_task_id: string;
  to_task_id: string; relation: string;
};

type Objective = {
  id: string; title: string; description: string;
  status: string; initiator: string; final_result: string;
  created_at: string; progress: number;
};

type Artifact = {
  artifact_id: string; task_id: string; author: string;
  title: string; content: string; created_at: string;
};

type RecordEnvelope = { id: string; fields: Record<string, unknown> };
type Verification = Record<string, unknown>;

type Snapshot = {
  mode: "real"; empty: boolean;
  base: { token_suffix: string };
  objective: Objective | null;
  workers: Worker[]; tasks: Task[]; edges: Edge[];
  claims: Record<string, unknown>[];
  messages: RecordEnvelope[];
  artifacts: Artifact[];
  verifications: Verification[];
  events: RecordEnvelope[];
  generated_at: string;
};

type DemoResult = {
  objective_id: string; tasks: Task[];
  all_tasks_completed: boolean;
  objective_completed: boolean;
  edge_count: number; verification_count: number;
};

type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError };

const STATUS_LABELS: Record<string, string> = {
  pending: "等待", claimed: "已领取", in_progress: "工作中",
  completed: "完成", failed: "失败", idle: "空闲", working: "工作中",
};

const EVENT_LABELS: Record<string, string> = {
  objective_planned: "目标拆解",
  objective_completed: "目标完成",
  task_claimed: "任务认领",
  task_completed: "任务完成",
  task_retry: "任务重试",
  task_lease_expired: "租约过期",
  task_verification_retry: "审核重做",
  task_verification_failed: "审核未过",
  task_execution_failed: "执行失败",
  planning_dependency_dropped: "依赖跳过",
};

const EVENT_TONE: Record<string, string> = {
  objective_planned: "eventTypeInfo",
  objective_completed: "eventTypeSuccess",
  task_claimed: "eventTypeInfo",
  task_completed: "eventTypeSuccess",
  task_retry: "eventTypeWarn",
  task_lease_expired: "eventTypeWarn",
  task_verification_retry: "eventTypeWarn",
  task_verification_failed: "eventTypeFail",
  task_execution_failed: "eventTypeFail",
  planning_dependency_dropped: "eventTypeWarn",
};

function eventTypeClass(eventType: string): string {
  return EVENT_TONE[eventType] || "eventTypeInfo";
}

function formatEventNarrative(eventType: string, actor: string, detail: string): string {
  const a = actor || "team-lead";
  switch (eventType) {
    case "objective_planned": return `Leader 已拆解目标：${detail.slice(0, 50)}`;
    case "objective_completed": return `目标已完成 · ${detail.slice(0, 40)}`;
    case "task_claimed": return `${a} 领取了任务`;
    case "task_completed": return `${a} 完成了任务`;
    case "task_retry": return `重试任务（${detail.slice(0, 40)}）`;
    case "task_lease_expired": return `${a} 的任务租约过期，已回收`;
    case "task_verification_retry": return `${a} 的产出未通过，安排重做`;
    case "task_verification_failed": return `${a} 的产出审核未通过`;
    case "task_execution_failed": return `${a} 任务执行失败`;
    case "planning_dependency_dropped": return `规划阶段跳过依赖：${detail.slice(0, 40)}`;
    default: return detail.slice(0, 60);
  }
}

/* ===== Main Page ===== */
export default function Home() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState("");
  const [view, setView] = useState<"monitor" | "mission">("monitor");
  const [showPanel, setShowPanel] = useState(true);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  /* Mission form state */
  const [objectiveTitle, setObjectiveTitle] = useState("");
  const [objectiveDescription, setObjectiveDescription] = useState("");
  const [maxTasks, setMaxTasks] = useState(4);
  const [workers, setWorkers] = useState(3);
  const [timeout, setTimeout_] = useState(600);
  const [runMode, setRunMode] = useState<"plan" | "full">("full");
  const [message, setMessage] = useState("");
  const [recipient, setRecipient] = useState("team-lead");
  const [operationToken, setOperationToken] = useState("");
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [tutorialOpen, setTutorialOpen] = useState(false);
  const loadingRef = useRef(false);
  const snapshotRef = useRef<Snapshot | null>(null);

  const flash = (msg: string, ok = true) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  };

  const loadSnapshot = async () => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    setLoading(true);
    try {
      const res = await fetch("/api/agent-team/snapshot", { cache: "no-store" });
      const payload = (await res.json()) as ApiResult<Snapshot>;
      if (!payload.ok) {
        setError(payload.error);
        if (!snapshotRef.current) setSnapshot(null);
      } else {
        snapshotRef.current = payload.data;
        setSnapshot(payload.data); setError(null);
        setLastUpdated(new Date().toLocaleTimeString());
      }
    } catch (err) {
      setError({ code: "CLIENT_FETCH", stage: "client",
        message: err instanceof Error ? err.message : "Fetch failed",
        detail: "", timestamp: new Date().toISOString() });
    } finally { loadingRef.current = false; setLoading(false); }
  };

  useEffect(() => {
    const t = window.setTimeout(() => {
      setOperationToken(window.sessionStorage.getItem("agent-team-operation-token") || "");
      const seen = window.localStorage.getItem("agent-team-tutorial-seen");
      if (!seen) setTutorialOpen(true);
    }, 0);
    window.setTimeout(() => void loadSnapshot(), 0);
    const timer = window.setInterval(() => void loadSnapshot(), 8000);
    return () => { window.clearTimeout(t); window.clearInterval(timer); };
  }, []);

  const dismissTutorial = () => {
    window.localStorage.setItem("agent-team-tutorial-seen", "1");
    setTutorialOpen(false);
  };

  const metrics = useMemo(() => {
    const counts: Record<string, number> = { pending: 0, claimed: 0, in_progress: 0, completed: 0, failed: 0 };
    snapshot?.tasks.forEach(t => { counts[t.status] = (counts[t.status] || 0) + 1; });
    return {
      workers: snapshot?.workers.length ?? 0,
      working: snapshot?.workers.filter(w => w.status === "working").length ?? 0,
      tasks: snapshot?.tasks.length ?? 0,
      completed: counts.completed,
      inProgress: counts.in_progress + counts.claimed,
      pending: counts.pending,
      failed: counts.failed,
      verifications: snapshot?.verifications.length ?? 0,
      counts,
    };
  }, [snapshot]);

  const selectedObjective = snapshot?.objective ?? null;
  const recipients = useMemo(() =>
    ["team-lead", ...(snapshot?.workers.map(w => w.id) ?? [])],
    [snapshot]);

  /* Actions */
  type ActionResult = ApiResult<unknown>;
  async function post(url: string, body: Record<string, unknown>): Promise<ActionResult> {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "content-type": "application/json",
          ...(operationToken ? { "x-agent-team-token": operationToken } : {}) },
        body: JSON.stringify(body),
      });
      return res.json() as Promise<ActionResult>;
    } catch (err) {
      return { ok: false, error: { code: "CLIENT_ACTION", stage: "client",
        message: err instanceof Error ? err.message : "Action failed",
        detail: "", timestamp: new Date().toISOString() }};
    }
  }

  async function submitObjective(e: FormEvent) {
    e.preventDefault();
    if (!objectiveTitle.trim() || !objectiveDescription.trim()) return;
    setBusyAction("objective");
    const result = await post("/api/agent-team/objectives", {
      title: objectiveTitle, description: objectiveDescription, maxTasks,
    });
    if (!result.ok) { setError(result.error); flash("启动失败", false); }
    else { setObjectiveTitle(""); setObjectiveDescription(""); flash("目标已创建"); await loadSnapshot(); }
    setBusyAction(null);
  }

  async function submitMessage(e: FormEvent) {
    e.preventDefault();
    if (!selectedObjective || !message.trim()) return;
    setBusyAction("message");
    const result = await post("/api/agent-team/messages", {
      objectiveId: selectedObjective.id, recipient, summary: "Console instruction", message,
    });
    if (!result.ok) { flash("发送失败", false); }
    else { setMessage(""); flash("指令已发送"); await loadSnapshot(); }
    setBusyAction(null);
  }

  async function recoverExpired() {
    if (!selectedObjective) return;
    setBusyAction("recover");
    const r1 = await post("/api/agent-team/recover-expired", { objectiveId: selectedObjective.id });
    const r2 = await post("/api/agent-team/retry-failed", { objectiveId: selectedObjective.id });
    const ok = r1.ok && r2.ok;
    flash(ok ? "已回收并重试" : "操作部分失败", ok);
    await loadSnapshot();
    setBusyAction(null);
  }

  async function runFullDemo(override?: { title: string; description: string; maxTasks?: number; workers?: number }) {
    const title = override?.title ?? objectiveTitle;
    const description = override?.description ?? objectiveDescription;
    if (!title.trim() || !description.trim()) return;
    setBusyAction("demo");
    flash("目标已下发，Worker 正在执行...", true);
    const result = await post("/api/agent-team/start-demo", {
      title, description,
      maxTasks: override?.maxTasks ?? maxTasks,
      workers: override?.workers ?? workers,
      timeout,
    });
    if (!result.ok) { setError(result.error); flash("启动失败", false); setBusyAction(null); return; }
    const data = (result as { ok: true; data: { objective_id: string; task_count: number; workers_spawned: unknown[] } }).data;
    flash(`目标已创建 · ${data.task_count} 个任务 · ${data.workers_spawned.length} 个 Worker 已启动`, true);
    if (!override) { setObjectiveTitle(""); setObjectiveDescription(""); }
    setView("monitor");
    setBusyAction(null);
    await loadSnapshot();
  }

  async function launchScenario(scenario: Scenario) {
    await runFullDemo({
      title: scenario.objectiveTitle,
      description: scenario.objectiveDescription,
      maxTasks: scenario.maxTasks,
      workers: scenario.workers,
    });
  }

  const connectionState = error ? "error" : snapshot?.empty ? "empty" : loading && !snapshot ? "loading" : "connected";

  return (
    <div className={`${styles.shell} ${!showPanel ? styles.shellNoPanel : ""}`}>
      {/* Sidebar */}
      <Sidebar
        view={view} setView={setView}
        connectionState={connectionState}
        metrics={metrics}
        onRefresh={() => void loadSnapshot()}
        onShowTutorial={() => setTutorialOpen(true)}
      />

      {/* Main */}
      <main className={`${styles.main} ${!showPanel ? styles.mainWide : ""}`}>
        {error && <ErrorBanner error={error} onDismiss={() => setError(null)} />}

        {view === "mission" ? (
          <MissionControl
            objectiveTitle={objectiveTitle} setObjectiveTitle={setObjectiveTitle}
            objectiveDescription={objectiveDescription} setObjectiveDescription={setObjectiveDescription}
            maxTasks={maxTasks} setMaxTasks={setMaxTasks}
            workers={workers} setWorkers={setWorkers}
            timeout={timeout} setTimeout_={setTimeout_}
            runMode={runMode} setRunMode={setRunMode}
            busyAction={busyAction}
            onLaunchScenario={launchScenario}
            onSubmitObjective={(e) => { e.preventDefault();
              runMode === "full" ? runFullDemo() : submitObjective(e); }}
          />
        ) : (
          <Monitor
            snapshot={snapshot} metrics={metrics}
            selectedObjective={selectedObjective} loading={loading}
            lastUpdated={lastUpdated} showPanel={showPanel}
            connectionState={connectionState}
            message={message} setMessage={setMessage}
            recipient={recipient} setRecipient={setRecipient}
            recipients={recipients}
            operationToken={operationToken} setOperationToken={setOperationToken}
            busyAction={busyAction}
            onSubmitMessage={submitMessage}
            onRecover={recoverExpired}
            onRefresh={() => void loadSnapshot()}
            onTogglePanel={() => setShowPanel(!showPanel)}
          />
        )}
      </main>

      {/* Right Panel */}
      {showPanel && view === "monitor" && (
        <RightPanel
          snapshot={snapshot}
          busyAction={busyAction}
          onRecover={recoverExpired}
        />
      )}

      {toast && <div className={`${styles.toast} ${toast.ok ? styles.toastOk : styles.toastErr}`}>{toast.msg}</div>}

      {tutorialOpen && (
        <TutorialOverlay
          onComplete={dismissTutorial}
          onJumpToMission={() => { dismissTutorial(); setView("mission"); }}
        />
      )}
    </div>
  );
}

/* ===== Sidebar ===== */
function Sidebar({ view, setView, connectionState, metrics, onRefresh, onShowTutorial }: {
  view: string; setView: (v: "monitor" | "mission") => void;
  connectionState: string; metrics: Metrics;
  onRefresh: () => void;
  onShowTutorial: () => void;
}) {
  return (
    <aside className={styles.sidebar}>
      <div className={styles.brand}>
        <div className={styles.brandIcon}><Terminal size={16} /></div>
        <span className={styles.brandText}>Command Center</span>
      </div>

      <div className={styles.navGroup}>
        <span className={styles.navLabel}>导航</span>
        <button
          className={`${styles.navItem} ${view === "monitor" ? styles.navItemActive : ""}`}
          onClick={() => setView("monitor")}
        >
          <Activity size={15} /> 任务看板
          {metrics.tasks > 0 && <span className={styles.navBadge}>{metrics.completed}/{metrics.tasks}</span>}
        </button>
        <button
          className={`${styles.navItem} ${view === "mission" ? styles.navItemActive : ""}`}
          onClick={() => setView("mission")}
        >
          <Zap size={15} /> 任务中心
        </button>
      </div>

      <div className={styles.navGroup}>
        <span className={styles.navLabel}>系统</span>
        <ConnectionStatus state={connectionState} />
        <button className={styles.navItem} onClick={onRefresh}>
          <RefreshCw size={15} /> 刷新数据
        </button>
        <button className={styles.navItem} onClick={onShowTutorial}>
          <HelpCircle size={15} /> 新手引导
        </button>
      </div>
    </aside>
  );
}

function ConnectionStatus({ state }: { state: string }) {
  const cls = state === "connected" ? styles.statusDotLive
    : state === "error" ? styles.statusDotDead : styles.statusDotIdle;
  const label = state === "connected" ? "已连接 Base" : state === "error" ? "连接异常" : "未连接";
  return (
    <div className={styles.navItem} style={{ cursor: "default" }}>
      <span className={`${styles.statusDot} ${cls}`} />
      <span>{label}</span>
    </div>
  );
}

/* ===== Monitor View ===== */
type Metrics = { workers: number; working: number; tasks: number; completed: number; inProgress: number; pending: number; failed: number; verifications: number; counts: Record<string, number> };

function Monitor({ snapshot, metrics, selectedObjective, loading, lastUpdated, connectionState, showPanel,
  message, setMessage, recipient, setRecipient, recipients, operationToken, setOperationToken,
  busyAction, onSubmitMessage, onRecover, onRefresh, onTogglePanel }: {
  snapshot: Snapshot | null; metrics: Metrics;
  selectedObjective: Objective | null; loading: boolean;
  lastUpdated: string; connectionState: string; showPanel: boolean;
  message: string; setMessage: (v: string) => void;
  recipient: string; setRecipient: (v: string) => void;
  recipients: string[];
  operationToken: string; setOperationToken: (v: string) => void;
  busyAction: string | null;
  onSubmitMessage: (e: FormEvent) => void;
  onRecover: () => void;
  onRefresh: () => void;
  onTogglePanel: () => void;
}) {
  return (
    <>
      {/* Top bar */}
      <div className={styles.topBar}>
        <div className={styles.statusRow}>
          <span className={`${styles.statusDot} ${connectionState === "connected" ? styles.statusDotLive : connectionState === "error" ? styles.statusDotDead : styles.statusDotIdle}`} />
          <span className={styles.statusLabel}>
            {connectionState === "connected" ? "Base 在线" : connectionState === "error" ? "连接异常" : "同步中..."}
          </span>
          <span className={styles.statusLabel}>·</span>
          <span className={styles.statusLabel}>{lastUpdated || "等待更新"}</span>
        </div>
        <div className={styles.topActions}>
          <button className={styles.btnIcon} onClick={onTogglePanel} title={showPanel ? "隐藏面板" : "显示面板"}>
            {showPanel ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
          <button className={styles.btnIcon} onClick={onRefresh} title="刷新">
            {loading ? <Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} /> : <RefreshCw size={16} />}
          </button>
        </div>
      </div>

      {/* Metrics */}
      <div className={styles.metricsGrid}>
        <MetricBox icon={<Users size={16} />} label="数字员工" value={metrics.workers} sub={`${metrics.working} 工作中`} tone="blue" />
        <MetricBox icon={<GitBranch size={16} />} label="任务" value={metrics.tasks} sub={`${metrics.completed} 完成 · ${metrics.inProgress} 进行中`} tone="green" />
        <MetricBox icon={<ShieldCheck size={16} />} label="质量验证" value={metrics.verifications} sub={metrics.failed > 0 ? `${metrics.failed} 失败` : "全部通过"} tone="warn" />
        <MetricBox icon={<Activity size={16} />} label="完成率" value={selectedObjective ? Math.round((selectedObjective.progress ?? 0) * 100) : 0} sub="%" tone="blue" />
      </div>

      {/* Objective */}
      {selectedObjective ? (
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <div className={styles.cardTitle}>
              <Cpu size={15} className={styles.cardTitleIcon} />
              当前目标
            </div>
            <span className={styles.progressLabel}>{selectedObjective.status}</span>
          </div>
          <h2 className={styles.objectiveTitle}>{selectedObjective.title}</h2>
          <p className={styles.objectiveDesc}>{selectedObjective.description}</p>
          <div className={styles.progressRow}>
            <span className={styles.progressPercent}>{Math.round((selectedObjective.progress ?? 0) * 100)}%</span>
            <div className={styles.progressTrack}>
              <div className={styles.progressFill} style={{ width: `${Math.round((selectedObjective.progress ?? 0) * 100)}%` }} />
            </div>
          </div>
          <StatusChips counts={metrics.counts} />
        </div>
      ) : (
        <EmptyState icon={<Cpu size={28} />} text="暂无目标记录 — 前往「任务中心」创建新目标" />
      )}

      {/* Tasks */}
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <div className={styles.cardTitle}>
            <GitBranch size={15} className={styles.cardTitleIcon} />
            任务流
          </div>
          <button className={styles.btnGhost} onClick={onRecover} disabled={busyAction === "recover" || !selectedObjective}>
            {busyAction === "recover" ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <RotateCcw size={14} />}
            回收重试
          </button>
        </div>
        {snapshot?.tasks.length ? (
          <div className={styles.taskList}>
            {snapshot.tasks.map(t => (
              <TaskCard key={t.id} task={t} edges={snapshot.edges} allTasks={snapshot.tasks} />
            ))}
          </div>
        ) : <EmptyState icon={<GitBranch size={20} />} text="暂无任务" />}
      </div>

      {/* Final Report */}
      {selectedObjective?.status === "completed" && selectedObjective.final_result && (
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <div className={styles.cardTitle}>
              <FileText size={15} className={styles.cardTitleIcon} />
              最终报告
            </div>
            <span className={styles.progressLabel}>已完成</span>
          </div>
          <div className={styles.reportContent}>
            {selectedObjective.final_result.split("\n").map((line, i) => {
              if (line.startsWith("# ")) return <h2 key={i} className={styles.reportH1}>{line.slice(2)}</h2>;
              if (line.startsWith("## ")) return <h3 key={i} className={styles.reportH2}>{line.slice(3)}</h3>;
              if (line.startsWith("### ")) return <h4 key={i} className={styles.reportH3}>{line.slice(4)}</h4>;
              if (line.startsWith("- ")) return <li key={i} className={styles.reportLi}>{line.slice(2)}</li>;
              if (line.startsWith("  - ")) return <li key={i} className={styles.reportLiSub}>{line.slice(4)}</li>;
              if (line.trim() === "") return <br key={i} />;
              return <p key={i} className={styles.reportP}>{line}</p>;
            })}
          </div>
        </div>
      )}

      {/* Artifacts */}
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <div className={styles.cardTitle}>
            <FileText size={15} className={styles.cardTitleIcon} />
            产物
          </div>
          <span className={styles.statusLabel}>{snapshot?.artifacts.length ?? 0} 件</span>
        </div>
        {snapshot?.artifacts.length ? (
          <ArtifactList artifacts={snapshot.artifacts.slice(-3).reverse()} />
        ) : <EmptyState icon={<FileText size={20} />} text="暂无产物" />}
      </div>

      {/* Footer */}
      <div className={styles.footer}>
        <span>Base ...{snapshot?.base.token_suffix || "—"}</span>
        <span>刷新: {lastUpdated || "—"}</span>
      </div>
    </>
  );
}

function MetricBox({ icon, label, value, sub, tone }: { icon: ReactNode; label: string; value: number; sub: string; tone: "blue" | "green" | "warn" }) {
  const iconCls = tone === "blue" ? styles.metricIconBlue : tone === "green" ? styles.metricIconGreen : styles.metricIconWarn;
  return (
    <div className={styles.metric}>
      <div className={`${styles.metricIcon} ${iconCls}`}>{icon}</div>
      <div className={styles.metricValue}>{value}{sub.startsWith("%") ? "%" : ""}</div>
      <div className={styles.metricLabel}>{label}{sub && !sub.startsWith("%") ? ` · ${sub}` : ""}</div>
    </div>
  );
}

function TaskCard({ task, edges, allTasks }: { task: Task; edges: Edge[]; allTasks: Task[] }) {
  const blockers = edges.filter(e => e.to_task_id === task.id);
  const blockedBy = edges.filter(e => e.from_task_id === task.id);
  const statusCls = task.status === "completed" ? styles.taskItemCompleted
    : task.status === "failed" ? styles.taskItemFailed
    : task.status === "in_progress" || task.status === "claimed" ? styles.taskItemActive : "";
  const dotCls = task.status === "completed" ? styles.taskStateCompleted
    : task.status === "failed" ? styles.taskStateFailed
    : task.status === "in_progress" || task.status === "claimed" ? styles.taskStateActive : styles.taskStatePending;
  const statusLabelCls = task.status === "completed" ? styles.taskStatusCompleted
    : task.status === "failed" ? styles.taskStatusFailed
    : task.status === "in_progress" || task.status === "claimed" ? styles.taskStatusActive : styles.taskStatusPending;
  const findTask = (id: string) => allTasks.find(t => t.id === id);

  return (
    <div className={`${styles.taskItem} ${statusCls}`}>
      <div className={styles.taskLeft}>
        <div className={`${styles.taskStateDot} ${dotCls}`} />
        <div className={styles.taskInfo}>
          <h4 className={styles.taskSubject}>{task.subject}</h4>
          <p className={styles.taskDesc}>{task.description.slice(0, 160)}</p>
          <div className={styles.taskMeta}>
            <span className={styles.taskTag}>{task.role}</span>
            {task.owner && <span className={`${styles.taskTag} ${styles.taskTagOwner}`}>{task.owner}</span>}
            {blockers.length > 0 && blockers.map(b => {
              const bt = findTask(b.from_task_id);
              return (
                <span key={b.id} className={styles.taskTagDep} title={(bt?.subject ?? b.from_task_id).slice(0, 80)}>
                  <ArrowRight size={11} /> {(bt?.subject ?? b.from_task_id).slice(0, 30)}
                </span>
              );
            })}
          </div>
        </div>
      </div>
      <div className={styles.taskRight}>
        <span className={`${styles.taskStatus} ${statusLabelCls}`}>{STATUS_LABELS[task.status] || task.status}</span>
        {task.attempt_count > 0 && <span className={styles.taskAttempts}>{task.attempt_count}x</span>}
      </div>
    </div>
  );
}

function ArtifactList({ artifacts }: { artifacts: Artifact[] }) {
  return (
    <div>
      {artifacts.map(a => (
        <ArtifactCard key={a.artifact_id} artifact={a} />
      ))}
    </div>
  );
}

function ArtifactCard({ artifact }: { artifact: Artifact }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className={styles.artifactCard}>
      <div className={styles.artifactTitle}>{artifact.title || artifact.artifact_id}</div>
      <div className={styles.artifactAuthor}>{artifact.author} · {artifact.created_at?.slice(0, 19) || ""}</div>
      <pre className={`${styles.artifactContent} ${expanded ? styles.artifactContentExpanded : ""}`}
        onClick={() => setExpanded(!expanded)}>
        {artifact.content}
      </pre>
    </div>
  );
}

/* ===== Right Panel ===== */
function RightPanel({ snapshot, busyAction, onRecover }: {
  snapshot: Snapshot | null; busyAction: string | null; onRecover: () => void;
}) {
  return (
    <aside className={styles.panel}>
      <div className={styles.panelHeader}>
        <span className={styles.panelLabel}>数字员工</span>
        <span className={styles.panelLabel}>{snapshot?.workers.length ?? 0} 位</span>
      </div>
      <div className={styles.workerList}>
        {snapshot?.workers.length ? snapshot.workers.map(w => (
          <div key={w.id} className={styles.workerCard}>
            <div className={`${styles.workerAvatar} ${w.status === "working" ? styles.workerAvatarActive : ""}`}>
              {w.role.slice(0, 2).toUpperCase()}
            </div>
            <div className={styles.workerBody}>
              <div className={styles.workerName}>{w.id}</div>
              <div className={styles.workerRole}>{w.role}</div>
              {w.current_task_id && <div className={styles.workerTask}>{w.current_task_id.slice(0, 20)}...</div>}
            </div>
            <div className={`${styles.workerStatus} ${w.status === "working" ? styles.workerActive : w.heartbeat_at && Date.now() - Date.parse(w.heartbeat_at) > 300_000 ? styles.workerGone : styles.workerIdle}`} />
          </div>
        )) : <EmptyState icon={<Users size={20} />} text="无在线员工" />}
      </div>

      <div className={styles.panelHeader} style={{ marginTop: 8 }}>
        <span className={styles.panelLabel}>最近事件</span>
      </div>
      <div className={styles.eventList}>
        {snapshot?.events.slice(-12).reverse().map(e => {
          const eventType = String(e.fields.event_type || "");
          const actor = String(e.fields.actor || e.fields["执行者"] || "");
          const detail = String(e.fields.detail || e.fields["详情"] || "");
          const narrative = formatEventNarrative(eventType, actor, detail);
          return (
            <div key={e.id} className={styles.eventItem} title={`${eventType} · ${detail}`}>
              <span className={`${styles.eventType} ${styles[eventTypeClass(eventType)] || ""}`}>
                {EVENT_LABELS[eventType] || eventType}
              </span>
              <span className={styles.eventDetail}>{narrative}</span>
              <span className={styles.eventTime}>{String(e.fields["创建时间"] || "").slice(11, 19)}</span>
            </div>
          );
        }) || <EmptyState icon={<Clock3 size={20} />} text="暂无事件" />}
      </div>

      <div className={styles.panelHeader} style={{ marginTop: 8 }}>
        <span className={styles.panelLabel}>质量闸门</span>
      </div>
      <div>
        {(snapshot?.verifications.slice(-6).reverse() || []).map((v, i) => {
          const verdict = String(v["结论"] || v.verdict || "—");
          const cls = verdict === "PASS" ? styles.verdictPass : verdict === "FAIL" ? styles.verdictFail : styles.verdictUnknown;
          return (
            <div key={i} className={styles.verificationItem}>
              <span className={cls}>{verdict}</span>
              <span className={styles.verificationDetail}>{String(v["问题"] || v.issues || "").slice(0, 80)}</span>
            </div>
          );
        })}
        {(!snapshot?.verifications.length) && <EmptyState icon={<ShieldCheck size={20} />} text="暂无验证" />}
      </div>

      <div style={{ marginTop: "auto", paddingTop: 16 }}>
        <button className={styles.btnDanger} style={{ width: "100%", justifyContent: "center" }}
          onClick={onRecover} disabled={busyAction === "recover" || !snapshot?.objective}>
          {busyAction === "recover" ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <RotateCcw size={14} />}
          回收过期 · 重试失败
        </button>
      </div>
    </aside>
  );
}

/* ===== Mission Control View ===== */
const SCENARIO_ICONS: Record<string, ReactNode> = {
  FileText: <FileText size={20} />,
  BarChart3: <BarChart3 size={20} />,
  Users: <Users size={20} />,
};

function MissionControl({ objectiveTitle, setObjectiveTitle, objectiveDescription,
  setObjectiveDescription, maxTasks, setMaxTasks, workers, setWorkers,
  timeout, setTimeout_, runMode, setRunMode, busyAction, onLaunchScenario, onSubmitObjective }: {
  objectiveTitle: string; setObjectiveTitle: (v: string) => void;
  objectiveDescription: string; setObjectiveDescription: (v: string) => void;
  maxTasks: number; setMaxTasks: (v: number) => void;
  workers: number; setWorkers: (v: number) => void;
  timeout: number; setTimeout_: (v: number) => void;
  runMode: string; setRunMode: (v: "plan" | "full") => void;
  busyAction: string | null;
  onLaunchScenario: (scenario: Scenario) => void;
  onSubmitObjective: (e: FormEvent) => void;
}) {
  const busy = busyAction !== null;
  const [customOpen, setCustomOpen] = useState(false);
  const [launchingId, setLaunchingId] = useState<string | null>(null);

  const handleLaunch = (scenario: Scenario) => {
    setLaunchingId(scenario.id);
    onLaunchScenario(scenario);
  };

  return (
    <div className={styles.missionForm}>
      <div style={{ marginBottom: 32 }}>
        <h2 style={{ fontSize: 22, fontWeight: 500, margin: "0 0 6px", color: "var(--text-primary)" }}>任务中心</h2>
        <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: 0 }}>
          选择业务场景，一键启动一个 AI 数字员工虚拟组织
        </p>
      </div>

      <div className={styles.scenarioGrid}>
        {SCENARIOS.map((scenario) => (
          <ScenarioCard
            key={scenario.id}
            scenario={scenario}
            launching={launchingId === scenario.id && busy}
            disabled={busy}
            onLaunch={() => handleLaunch(scenario)}
          />
        ))}
      </div>

      <button
        type="button"
        className={styles.customToggle}
        onClick={() => setCustomOpen(!customOpen)}
      >
        {customOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span>自定义目标 — 不使用预置场景</span>
      </button>

      {customOpen && (
        <form onSubmit={onSubmitObjective} className={styles.customForm}>
          <div className={styles.formSection}>
            <h3 className={styles.formSectionTitle}>目标定义</h3>
            <div className={styles.formField}>
              <label className={styles.formLabel}>目标标题</label>
              <input className={styles.inputBare} value={objectiveTitle}
                onChange={e => setObjectiveTitle(e.target.value)}
                placeholder="例如：撰写一份 Q2 行业分析报告" />
            </div>
            <div className={styles.formField}>
              <label className={styles.formLabel}>目标描述</label>
              <textarea className={styles.textareaBare} value={objectiveDescription}
                onChange={e => setObjectiveDescription(e.target.value)}
                placeholder="详细描述目标任务，包括具体需要覆盖的领域、产出要求、约束条件等..."
                rows={5} />
            </div>
          </div>

          <div className={styles.formSection}>
            <h3 className={styles.formSectionTitle}>执行参数</h3>
            <div className={styles.formRow}>
              <div className={styles.formField}>
                <label className={styles.formLabel}>最大任务数</label>
                <select className={styles.selectBare} value={maxTasks}
                  onChange={e => setMaxTasks(Number(e.target.value))}>
                  {[3, 4, 5, 6, 7].map(n => <option key={n} value={n}>{n} 个任务</option>)}
                </select>
              </div>
              <div className={styles.formField}>
                <label className={styles.formLabel}>Worker 数量</label>
                <select className={styles.selectBare} value={workers}
                  onChange={e => setWorkers(Number(e.target.value))}>
                  {[1, 2, 3, 4, 5].map(n => <option key={n} value={n}>{n} 个 worker</option>)}
                </select>
              </div>
            </div>
            <div className={styles.formRow}>
              <div className={styles.formField}>
                <label className={styles.formLabel}>超时时间</label>
                <select className={styles.selectBare} value={timeout}
                  onChange={e => setTimeout_(Number(e.target.value))}>
                  {[300, 600, 900, 1200].map(n => <option key={n} value={n}>{n}s ({Math.round(n / 60)}分钟)</option>)}
                </select>
              </div>
              <div className={styles.formField}>
                <label className={styles.formLabel}>运行模式</label>
                <select className={styles.selectBare} value={runMode}
                  onChange={e => setRunMode(e.target.value as "plan" | "full")}>
                  <option value="full">完整执行 (Leader 规划 + Worker 执行)</option>
                  <option value="plan">仅规划 (Leader 拆任务)</option>
                </select>
              </div>
            </div>
          </div>

          <div style={{ display: "flex", gap: 12, marginTop: 24 }}>
            <button className={styles.btnPrimary} type="submit" disabled={busy || !objectiveTitle.trim()}
              style={{ fontSize: 14, padding: "10px 28px" }}>
              {busy ? <Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} /> : <Play size={16} />}
              {busy ? "执行中..." : runMode === "full" ? "启动完整任务" : "开始规划"}
            </button>
            <button className={styles.btnGhost} type="button"
              onClick={() => { setObjectiveTitle(""); setObjectiveDescription(""); }}>
              清空
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

function ScenarioCard({ scenario, launching, disabled, onLaunch }: {
  scenario: Scenario; launching: boolean; disabled: boolean; onLaunch: () => void;
}) {
  return (
    <div className={`${styles.scenarioCard} ${launching ? styles.scenarioCardLaunching : ""}`}>
      <div className={styles.scenarioHeader}>
        <div className={styles.scenarioIcon}>{SCENARIO_ICONS[scenario.iconName]}</div>
        <span className={styles.scenarioMeta}>~{scenario.estimatedMinutes}min</span>
      </div>
      <h3 className={styles.scenarioTitle}>{scenario.title}</h3>
      <p className={styles.scenarioTagline}>{scenario.tagline}</p>
      <p className={styles.scenarioDesc}>{scenario.description}</p>
      <div className={styles.scenarioRoles}>
        {scenario.roles.map((r) => (
          <span key={r.id} className={styles.scenarioRole}>{r.label}</span>
        ))}
      </div>
      <button
        type="button"
        className={styles.scenarioBtn}
        disabled={disabled}
        onClick={onLaunch}
      >
        {launching ? (
          <><Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> 启动中</>
        ) : (
          <><Sparkles size={14} /> 一键启动</>
        )}
      </button>
    </div>
  );
}

/* ===== Shared Components ===== */
function ErrorBanner({ error, onDismiss }: { error: ApiError; onDismiss: () => void }) {
  return (
    <div className={styles.errorBanner}>
      <AlertTriangle size={18} className={styles.errorBannerIcon} />
      <div style={{ flex: 1 }}>
        <h3 className={styles.errorBannerTitle}>控制面板不可用</h3>
        <p className={styles.errorBannerMsg}>{error.message}</p>
        <div className={styles.errorBannerMeta}>
          <code>{error.stage}</code>
          <code>{error.code}</code>
        </div>
      </div>
      <button className={styles.btnIcon} onClick={onDismiss}><X size={14} /></button>
    </div>
  );
}

function StatusChips({ counts }: { counts: Record<string, number> }) {
  const STATUS_CONFIG: Record<string, { label: string; cls: string }> = {
    completed: { label: "已完成", cls: "chipCompleted" },
    in_progress: { label: "工作中", cls: "chipActive" },
    claimed: { label: "已领取", cls: "chipClaimed" },
    pending: { label: "等待中", cls: "chipPending" },
    failed: { label: "失败", cls: "chipFailed" },
  };
  const order = ["failed", "pending", "claimed", "in_progress", "completed"];
  return (
    <div className={styles.statusChips}>
      {order.map(status => {
        const count = counts[status] || 0;
        if (count === 0) return null;
        const cfg = STATUS_CONFIG[status];
        return (
          <span key={status} className={`${styles.chip} ${styles[cfg.cls]}`}>
            {cfg.label} <strong>{count}</strong>
          </span>
        );
      })}
    </div>
  );
}

function EmptyState({ icon, text }: { icon: ReactNode; text: string }) {
  return (
    <div className={styles.emptyState}>
      <div className={styles.emptyStateIcon}>{icon}</div>
      <div>{text}</div>
    </div>
  );
}

/* ===== Tutorial Overlay ===== */
const TUTORIAL_STEPS = [
  {
    icon: <Sparkles size={32} />,
    title: "欢迎来到 AI 数字员工指挥中心",
    body: (
      <>
        <p>这是一个由 <strong>多个 AI Agent</strong> 组成的虚拟组织。</p>
        <p>每个 Agent 扮演不同岗位（运营、编辑、审核、分析师等），通过<strong>飞书多维表格</strong>协同工作，自动完成业务目标。</p>
        <p style={{ marginTop: 12, color: "var(--text-secondary)", fontSize: 13 }}>
          只需 30 秒，就能看到一个完整的虚拟员工团队跑起来。
        </p>
      </>
    ),
  },
  {
    icon: <Activity size={32} />,
    title: "任务看板：实时观察组织运转",
    body: (
      <>
        <p>左侧导航的<strong>「任务看板」</strong>展示了：</p>
        <ul>
          <li>当前目标进度与状态分布</li>
          <li>任务依赖链 + 每个任务的负责人</li>
          <li>每位数字员工的实时状态</li>
          <li>质量审核结果（PASS / FAIL）</li>
          <li>目标完成时自动生成的<strong>最终报告</strong></li>
        </ul>
      </>
    ),
  },
  {
    icon: <Zap size={32} />,
    title: "任务中心：一键启动业务场景",
    body: (
      <>
        <p>「任务中心」预置了 <strong>3 个真实业务场景</strong>：</p>
        <ul>
          <li>📰 内容运营周报团队</li>
          <li>📊 产品调研报告团队</li>
          <li>👥 招聘候选人评估团队</li>
        </ul>
        <p style={{ marginTop: 8 }}>
          点击任意场景的<strong>「一键启动」</strong>，AI 团队立刻开始工作，几分钟后即可看到完整产出。
        </p>
      </>
    ),
  },
  {
    icon: <CheckCircle2 size={32} />,
    title: "准备好了吗？",
    body: (
      <>
        <p>系统会自动：</p>
        <ul>
          <li>✓ Leader 分析目标，拆解为子任务</li>
          <li>✓ Worker 自主认领任务、并行执行</li>
          <li>✓ LLM 审核每份产出的质量</li>
          <li>✓ 失败自动重试，过期租约自动回收</li>
          <li>✓ 全部完成后生成项目总结报告</li>
        </ul>
        <p style={{ marginTop: 12, fontSize: 13, color: "var(--text-secondary)" }}>
          所有数据通过飞书 Base API 实时持久化，可随时查看历史。
        </p>
      </>
    ),
  },
];

function TutorialOverlay({ onComplete, onJumpToMission }: {
  onComplete: () => void;
  onJumpToMission: () => void;
}) {
  const [step, setStep] = useState(0);
  const total = TUTORIAL_STEPS.length;
  const current = TUTORIAL_STEPS[step];
  const isLast = step === total - 1;

  return (
    <div className={styles.tutorialBackdrop} onClick={onComplete}>
      <div className={styles.tutorialCard} onClick={(e) => e.stopPropagation()}>
        <button className={styles.tutorialClose} onClick={onComplete} aria-label="关闭">
          <X size={16} />
        </button>

        <div className={styles.tutorialIcon}>{current.icon}</div>
        <h2 className={styles.tutorialTitle}>{current.title}</h2>
        <div className={styles.tutorialBody}>{current.body}</div>

        <div className={styles.tutorialDots}>
          {TUTORIAL_STEPS.map((_, i) => (
            <span
              key={i}
              className={`${styles.tutorialDot} ${i === step ? styles.tutorialDotActive : ""}`}
              onClick={() => setStep(i)}
            />
          ))}
        </div>

        <div className={styles.tutorialActions}>
          <button className={styles.btnGhost} onClick={onComplete}>跳过</button>
          {step > 0 && (
            <button className={styles.btnGhost} onClick={() => setStep(step - 1)}>
              上一步
            </button>
          )}
          {!isLast ? (
            <button className={styles.btnPrimary} onClick={() => setStep(step + 1)}>
              下一步 <ArrowRight size={14} />
            </button>
          ) : (
            <button className={styles.btnPrimary} onClick={onJumpToMission}>
              <Sparkles size={14} /> 立即体验
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
