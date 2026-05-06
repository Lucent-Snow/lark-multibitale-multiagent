"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, X } from "lucide-react";

type Props = {
  objectiveCompleted: boolean;
  objectiveTitle: string | null;
  startedAt: string | null;
  completedAt: string | null;
  taskCount: number;
  verificationCount: number;
  onDismiss: () => void;
};

/** Confetti-style particles using CSS keyframes. */
const PARTICLE_COLORS = ["#60a5fa", "#34d399", "#f472b6", "#fbbf24", "#a78bfa", "#f87171"];

function randomParticles(n: number) {
  return Array.from({ length: n }, (_, i) => ({
    id: i,
    left: `${Math.random() * 100}%`,
    color: PARTICLE_COLORS[i % PARTICLE_COLORS.length],
    delay: `${Math.random() * 2}s`,
    size: `${4 + Math.random() * 8}px`,
  }));
}

export default function CelebrationOverlay({
  objectiveCompleted,
  objectiveTitle,
  startedAt,
  completedAt,
  taskCount,
  verificationCount,
  onDismiss,
}: Props) {
  const [visible, setVisible] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (objectiveCompleted && !dismissed) {
      const t = setTimeout(() => setVisible(true), 300);
      return () => clearTimeout(t);
    }
  }, [objectiveCompleted, dismissed]);

  if (!visible || dismissed) return null;

  let elapsed = "";
  if (startedAt && completedAt) {
    const start = Date.parse(startedAt);
    const end = Date.parse(completedAt);
    if (!isNaN(start) && !isNaN(end)) {
      const diff = Math.max(0, end - start);
      const mins = Math.floor(diff / 60000);
      const secs = Math.floor((diff % 60000) / 1000);
      elapsed = `${mins} 分 ${secs} 秒`;
    }
  }

  const particles = randomParticles(50);

  const handleDismiss = () => {
    setVisible(false);
    setDismissed(true);
    onDismiss();
    // Reset after a delay to allow re-show
    setTimeout(() => setDismissed(false), 5000);
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        background: "rgba(0,0,0,0.7)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        animation: "celebrationFadeIn 0.5s ease",
      }}
      onClick={handleDismiss}
    >
      {/* Particles */}
      {particles.map((p) => (
        <div
          key={p.id}
          style={{
            position: "absolute",
            left: p.left,
            top: "-10px",
            width: p.size,
            height: p.size,
            borderRadius: "50%",
            background: p.color,
            animation: `celebrationFall 3s ease-in ${p.delay} forwards`,
            opacity: 0,
          }}
        />
      ))}

      {/* Card */}
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--surface-raised, #1a1d2e)",
          border: "1px solid var(--border-default, #2a2d3e)",
          borderRadius: 16,
          padding: "40px 48px",
          textAlign: "center",
          maxWidth: 480,
          width: "90%",
          animation: "celebrationScale 0.5s ease",
          zIndex: 101,
        }}
      >
        <CheckCircle2
          size={56}
          style={{ color: "var(--accent-green, #34d399)", marginBottom: 16 }}
        />
        <h1
          style={{
            fontSize: 28,
            fontWeight: 700,
            color: "var(--text-primary)",
            margin: "0 0 8px",
          }}
        >
          目标完成！
        </h1>
        {objectiveTitle && (
          <p style={{ fontSize: 15, color: "var(--text-secondary)", margin: "0 0 20px" }}>
            {objectiveTitle}
          </p>
        )}
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            gap: 24,
            marginBottom: 24,
          }}
        >
          <div>
            <div style={{ fontSize: 24, fontWeight: 700, color: "var(--text-primary)" }}>
              {taskCount}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>任务完成</div>
          </div>
          <div>
            <div style={{ fontSize: 24, fontWeight: 700, color: "var(--text-primary)" }}>
              {verificationCount}
            </div>
            <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>质量验证</div>
          </div>
          {elapsed && (
            <div>
              <div style={{ fontSize: 24, fontWeight: 700, color: "var(--text-primary)" }}>
                {elapsed.split(" ")[0]}
              </div>
              <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                {elapsed.split(" ").slice(1).join(" ")}
              </div>
            </div>
          )}
        </div>
        <button
          onClick={handleDismiss}
          style={{
            background: "var(--accent-blue, #3b82f6)",
            color: "#fff",
            border: "none",
            borderRadius: 8,
            padding: "10px 32px",
            fontSize: 14,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          关闭
        </button>
      </div>
    </div>
  );
}
