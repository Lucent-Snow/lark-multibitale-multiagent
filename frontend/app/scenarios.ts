export type ScenarioRole = {
  id: string;
  role: string;
  label: string;
};

export type Scenario = {
  id: string;
  iconName: "FileText" | "BarChart3" | "Users";
  title: string;
  tagline: string;
  description: string;
  objectiveTitle: string;
  objectiveDescription: string;
  roles: ScenarioRole[];
  maxTasks: number;
  workers: number;
  estimatedMinutes: number;
};

// Keep the objective brief open-ended so the Leader can plan freely instead
// of executing a hand-written SOP. The card description is what the user sees;
// the objective text is what gets sent to the LLM.
export const SCENARIOS: Scenario[] = [
  {
    id: "tech-weekly",
    iconName: "FileText",
    title: "科技周报",
    tagline: "调研 → 撰稿 → 审核",
    description: "AI 团队自己分工：拆主题、查资料、写稿、互审，最后给一份能直接发的周报。",
    objectiveTitle: "本周科技产业周报",
    objectiveDescription:
      "面向科技行业读者，整理一份本周值得关注的科技动态周报。具体覆盖哪些方向、章节如何安排、字数和深浅由团队自行决定，最终交付一份可直接发布的周报。",
    roles: [
      { id: "researcher", role: "researcher", label: "研究员" },
      { id: "editor", role: "editor", label: "主笔" },
      { id: "reviewer", role: "reviewer", label: "审核" },
    ],
    maxTasks: 4,
    workers: 3,
    estimatedMinutes: 6,
  },
  {
    id: "market-research",
    iconName: "BarChart3",
    title: "市场调研",
    tagline: "盘点 → 对比 → 给结论",
    description: "团队自主选题、定维度、做对比，最后产出一份带建议的调研报告。",
    objectiveTitle: "AI 产品市场调研报告",
    objectiveDescription:
      "为产品决策者准备一份 AI 相关市场的调研报告。研究范围、对比维度、结论形式由团队自行设计，最终给出可决策的洞察与建议。",
    roles: [
      { id: "researcher", role: "researcher", label: "调研员" },
      { id: "analyst", role: "analyst", label: "分析师" },
      { id: "reviewer", role: "reviewer", label: "审核" },
    ],
    maxTasks: 4,
    workers: 3,
    estimatedMinutes: 7,
  },
  {
    id: "candidate-eval",
    iconName: "Users",
    title: "候选人评估",
    tagline: "建框架 → 逐项打分 → 录用建议",
    description: "团队自己定打分维度、做评估、给录用建议，输出一份完整的人才评估报告。",
    objectiveTitle: "高级工程师候选人评估",
    objectiveDescription:
      "为一位高级工程师候选人产出一份结构化的录用评估报告。评估维度、打分标准、是否给出培养建议都由团队自定，最终给出明确的录用建议与依据。",
    roles: [
      { id: "analyst", role: "analyst", label: "画像" },
      { id: "researcher", role: "researcher", label: "面试" },
      { id: "reviewer", role: "reviewer", label: "评委" },
    ],
    maxTasks: 4,
    workers: 3,
    estimatedMinutes: 6,
  },
];
