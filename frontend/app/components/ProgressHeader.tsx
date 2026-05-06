"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  objectiveTitle: string | null;
  progress: number; // 0–1
  completed: number;
  total: number;
  isComplete: boolean;
  startedAt: string | null; // ISO timestamp
  onToggleFullscreen: () => void;
  isFullscreen: boolean;
};

export default function ProgressHeader({
  objectiveTitle,
  progress,
  completed,
  total,
  isComplete,
  startedAt,
  onToggleFullscreen,
  isFullscreen,
}: Props) {
  const [elapsed, setElapsed] = useState("");
  const raf = useRef(0);

  useEffect(() => {
    if (!startedAt || isComplete) return;
    const start = Date.parse(startedAt);
    if (isNaN(start)) return;

    const tick = () => {
      const diff = Math.max(0, Date.now() - start);
      const mins = Math.floor(diff / 60000);
      const secs = Math.floor((diff % 60000) / 1000);
      setElapsed(`${mins}:${String(secs).padStart(2, "0")}`);
      raf.current = requestAnimationFrame(tick);
    };
    tick();
    return () => cancelAnimationFrame(raf.current);
  }, [startedAt, isComplete]);

  if (!objectiveTitle) return null;

  const pct = Math.round(progress * 100);

  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 50,
        background: "var(--surface-raised, #1a1d2e)",
        borderBottom: "1px solid var(--border-default, #2a2d3e)",
        padding: "10px 20px",
        display: "flex",
        alignItems: "center",
        gap: 16,
      }}
    >
      {/* Title */}
      <span
        style={{
          fontWeight: 600,
          fontSize: isFullscreen ? 18 : 14,
          color: "var(--text-primary)",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
          flex: 1,
        }}
      >
        {objectiveTitle}
      </span>

      {/* Progress bar */}
      <div
        style={{
          width: isFullscreen ? 200 : 140,
          height: 6,
          background: "var(--surface-inset, #0f0f1a)",
          borderRadius: 3,
          overflow: "hidden",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${pct}%`,
            background: pct === 100
              ? "var(--accent-green, #34d399)"
              : "var(--accent-blue, #60a5fa)",
            borderRadius: 3,
            transition: "width 0.6s ease",
          }}
        />
      </div>

      {/* Counts */}
      <span
        style={{
          fontSize: isFullscreen ? 16 : 13,
          fontWeight: 600,
          color: "var(--text-primary)",
          whiteSpace: "nowrap",
        }}
      >
        {completed}/{total}
      </span>

      {/* Percent */}
      <span
        style={{
          fontSize: isFullscreen ? 16 : 13,
          fontWeight: 700,
          color: pct === 100 ? "var(--accent-green, #34d399)" : "var(--accent-blue, #60a5fa)",
          whiteSpace: "nowrap",
          minWidth: 40,
          textAlign: "right",
        }}
      >
        {pct}%
      </span>

      {/* Elapsed */}
      {elapsed && (
        <span
          style={{
            fontSize: isFullscreen ? 14 : 12,
            color: "var(--text-secondary)",
            whiteSpace: "nowrap",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {elapsed}
        </span>
      )}

      {/* Fullscreen toggle */}
      <button
        onClick={onToggleFullscreen}
        title={isFullscreen ? "退出投屏" : "投屏模式"}
        style={{
          background: "none",
          border: "1px solid var(--border-default, #2a2d3e)",
          borderRadius: 6,
          color: "var(--text-secondary)",
          cursor: "pointer",
          padding: "4px 10px",
          fontSize: 12,
        }}
      >
        {isFullscreen ? "退出投屏" : "投屏"}
      </button>
    </header>
  );
}
