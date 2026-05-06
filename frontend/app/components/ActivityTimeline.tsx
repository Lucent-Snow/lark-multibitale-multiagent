"use client";

import { useEffect, useRef, useState } from "react";
import { Clock3 } from "lucide-react";

type Envelope = {
  id: string;
  fields: Record<string, unknown>;
};

type Props = {
  events: Envelope[];
  isFullscreen: boolean;
};

const EVENT_LABELS: Record<string, string> = {
  objective_planned: "拆解目标",
  objective_completed: "目标完成",
  task_claimed: "领取任务",
  task_completed: "完成任务",
  task_retry: "重试任务",
  task_lease_expired: "租约过期",
  task_verification_retry: "审核重做",
  task_verification_failed: "审核未过",
  task_execution_failed: "执行失败",
  planning_dependency_dropped: "跳过依赖",
};

const TONE_COLORS: Record<string, string> = {
  objective_planned: "#60a5fa",
  objective_completed: "#34d399",
  task_claimed: "#60a5fa",
  task_completed: "#34d399",
  task_retry: "#fbbf24",
  task_lease_expired: "#fbbf24",
  task_verification_retry: "#fbbf24",
  task_verification_failed: "#f87171",
  task_execution_failed: "#f87171",
  planning_dependency_dropped: "#fbbf24",
};

function formatNarrative(eventType: string, actor: string, detail: string): string {
  const a = actor || "team-lead";
  switch (eventType) {
    case "objective_planned": return `拆解目标：${detail.slice(0, 50)}`;
    case "objective_completed": return `目标完成 · ${detail.slice(0, 40)}`;
    case "task_claimed": return `${a} 领取了任务`;
    case "task_completed": return `${a} 完成了任务`;
    case "task_retry": return `重试任务 (${detail.slice(0, 40)})`;
    case "task_lease_expired": return `${a} 的租约过期已回收`;
    case "task_verification_retry": return `${a} 审核未通过，安排重做`;
    case "task_verification_failed": return `${a} 审核失败`;
    case "task_execution_failed": return `${a} 执行异常`;
    default: return detail.slice(0, 60);
  }
}

export default function ActivityTimeline({ events, isFullscreen }: Props) {
  const [newIds, setNewIds] = useState<Set<string>>(new Set());
  const prevCount = useRef(0);

  useEffect(() => {
    if (events.length > prevCount.current) {
      const incoming = events.slice(prevCount.current);
      setNewIds(new Set(incoming.map((e) => e.id)));
      const t = setTimeout(() => setNewIds(new Set()), 2000);
      prevCount.current = events.length;
      return () => clearTimeout(t);
    }
    prevCount.current = events.length;
  }, [events]);

  const visible = events.slice(isFullscreen ? -20 : -12);

  if (visible.length === 0) {
    return (
      <div
        style={{
          textAlign: "center",
          padding: 24,
          color: "var(--text-secondary)",
          fontSize: 13,
        }}
      >
        <Clock3 size={20} style={{ marginBottom: 8 }} />
        <div>暂无事件</div>
      </div>
    );
  }

  return (
    <div style={{ position: "relative", paddingLeft: 24 }}>
      {/* Vertical line */}
      <div
        style={{
          position: "absolute",
          left: 7,
          top: 0,
          bottom: 0,
          width: 2,
          background: "var(--border-default, #2a2d3e)",
        }}
      />

      {visible.map((e, i) => {
        const eventType = String(e.fields.event_type || "");
        const actor = String(e.fields.actor || e.fields["执行者"] || "");
        const detail = String(e.fields.detail || e.fields["详情"] || "");
        const color = TONE_COLORS[eventType] || "#6b7280";
        const narrative = formatNarrative(eventType, actor, detail);
        const isNew = newIds.has(e.id);

        return (
          <div
            key={e.id}
            style={{
              position: "relative",
              padding: "6px 0 6px 16px",
              marginBottom: 4,
              fontSize: isFullscreen ? 14 : 12,
              color: "var(--text-secondary)",
              animation: isNew ? "timelineFadeIn 0.5s ease" : undefined,
            }}
          >
            {/* Dot */}
            <div
              style={{
                position: "absolute",
                left: -20,
                top: 10,
                width: 10,
                height: 10,
                borderRadius: "50%",
                background: color,
                boxShadow: isNew ? `0 0 8px ${color}` : undefined,
              }}
            />
            <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>
              {EVENT_LABELS[eventType] || eventType}
            </span>{" "}
            <span>{narrative}</span>
            <span
              style={{
                display: "block",
                fontSize: isFullscreen ? 12 : 10,
                color: "var(--text-tertiary)",
                marginTop: 1,
              }}
            >
              {String(e.fields["创建时间"] || "").slice(11, 19)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
