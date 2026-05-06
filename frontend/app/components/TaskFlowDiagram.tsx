"use client";

import type { ReactNode } from "react";

type Task = {
  id: string;
  subject: string;
  role: string;
  status: string;
  owner: string;
};

type Edge = {
  id: string;
  from_task_id: string;
  to_task_id: string;
};

type Props = {
  tasks: Task[];
  edges: Edge[];
  isFullscreen: boolean;
};

const STATUS_COLORS: Record<string, string> = {
  completed: "#34d399",
  in_progress: "#60a5fa",
  claimed: "#fbbf24",
  pending: "#6b7280",
  failed: "#f87171",
};

/** Simple layered layout: root tasks first, then each layer adds blocked tasks. */
function layoutLayers(tasks: Task[], edges: Edge[]) {
  const taskMap = new Map(tasks.map((t) => [t.id, t]));
  const children = new Map<string, string[]>();
  const parents = new Map<string, string[]>();
  for (const e of edges) {
    if (!children.has(e.from_task_id)) children.set(e.from_task_id, []);
    children.get(e.from_task_id)!.push(e.to_task_id);
    if (!parents.has(e.to_task_id)) parents.set(e.to_task_id, []);
    parents.get(e.to_task_id)!.push(e.from_task_id);
  }

  // BFS from root tasks
  const layers: string[][] = [];
  const placed = new Set<string>();
  let frontier = tasks.filter((t) => !parents.has(t.id) || parents.get(t.id)!.length === 0).map((t) => t.id);

  while (frontier.length > 0) {
    layers.push(frontier);
    frontier.forEach((id) => placed.add(id));
    const next: string[] = [];
    for (const id of frontier) {
      for (const child of children.get(id) || []) {
        if (placed.has(child)) continue;
        const deps = parents.get(child) || [];
        if (deps.every((d) => placed.has(d))) {
          next.push(child);
        }
      }
    }
    frontier = [...new Set(next)];
  }

  // Any stragglers
  const stragglers = tasks.map((t) => t.id).filter((id) => !placed.has(id));
  if (stragglers.length) layers.push(stragglers);

  return layers;
}

export default function TaskFlowDiagram({ tasks, edges, isFullscreen }: Props) {
  if (tasks.length === 0) return null;

  const layers = layoutLayers(tasks, edges);
  const taskMap = new Map(tasks.map((t) => [t.id, t]));

  const nodeW = isFullscreen ? 180 : 140;
  const nodeH = isFullscreen ? 64 : 50;
  const layerGapY = isFullscreen ? 100 : 80;
  const nodeGapX = isFullscreen ? 24 : 16;
  const padding = isFullscreen ? 32 : 20;

  let maxNodesInLayer = 0;
  for (const layer of layers) {
    if (layer.length > maxNodesInLayer) maxNodesInLayer = layer.length;
  }

  const totalW = maxNodesInLayer * (nodeW + nodeGapX) - nodeGapX + padding * 2;
  const totalH = layers.length * (nodeH + layerGapY) - layerGapY + padding * 2;

  // Build node positions
  const positions = new Map<string, { x: number; y: number }>();
  for (let li = 0; li < layers.length; li++) {
    const layer = layers[li];
    const rowWidth = layer.length * (nodeW + nodeGapX) - nodeGapX;
    const offsetX = (totalW - rowWidth) / 2;
    for (let ni = 0; ni < layer.length; ni++) {
      positions.set(layer[ni], {
        x: offsetX + ni * (nodeW + nodeGapX),
        y: padding + li * (nodeH + layerGapY),
      });
    }
  }

  const arrows: ReactNode[] = [];
  for (const edge of edges) {
    const from = positions.get(edge.from_task_id);
    const to = positions.get(edge.to_task_id);
    if (!from || !to) continue;
    const x1 = from.x + nodeW / 2;
    const y1 = from.y + nodeH;
    const x2 = to.x + nodeW / 2;
    const y2 = to.y;
    const midY = (y1 + y2) / 2;
    const d = `M${x1},${y1} C${x1},${midY} ${x2},${midY} ${x2},${y2}`;
    arrows.push(
      <path
        key={edge.id}
        d={d}
        stroke="#4b5563"
        strokeWidth={1.5}
        fill="none"
        markerEnd="url(#arrowhead)"
      />
    );
  }

  return (
    <svg
      viewBox={`0 0 ${totalW} ${totalH}`}
      style={{ width: "100%", height: "auto", maxHeight: isFullscreen ? 500 : 400 }}
    >
      <defs>
        <marker
          id="arrowhead"
          viewBox="0 0 10 10"
          refX={10}
          refY={5}
          markerWidth={6}
          markerHeight={6}
          orient="auto-start-reverse"
        >
          <path d="M0,0 L10,5 L0,10 Z" fill="#4b5563" />
        </marker>
      </defs>

      {arrows}

      {tasks.map((task) => {
        const pos = positions.get(task.id);
        if (!pos) return null;
        const color = STATUS_COLORS[task.status] || "#6b7280";
        const isActive = task.status === "in_progress" || task.status === "claimed";
        return (
          <g key={task.id}>
            <rect
              x={pos.x}
              y={pos.y}
              width={nodeW}
              height={nodeH}
              rx={8}
              ry={8}
              fill="var(--surface-raised, #1a1d2e)"
              stroke={color}
              strokeWidth={isActive ? 2.5 : 1.5}
              style={
                isActive
                  ? { animation: "nodePulse 2s ease-in-out infinite" }
                  : undefined
              }
            />
            <text
              x={pos.x + nodeW / 2}
              y={pos.y + 18}
              textAnchor="middle"
              fill="#e5e7eb"
              fontSize={isFullscreen ? 13 : 11}
              fontWeight={600}
            >
              {task.subject.slice(0, isFullscreen ? 18 : 14)}
            </text>
            <text
              x={pos.x + nodeW / 2}
              y={pos.y + nodeH - 10}
              textAnchor="middle"
              fill={color}
              fontSize={isFullscreen ? 11 : 10}
            >
              {task.role}
              {task.owner ? ` · ${task.owner.slice(0, 8)}` : ""}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
