/**
 * Pre-configured business scenarios for one-click demo launch.
 * Each scenario is a complete virtual organization with role assignments and a concrete objective.
 */

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

export const SCENARIOS: Scenario[] = [
  {
    id: "content-ops-weekly",
    iconName: "FileText",
    title: "内容运营周报团队",
    tagline: "运营 · 编辑 · 审核 · 三角色协作",
    description:
      "运营主管拆解一周选题方向，内容编辑撰写本周稿件，质量审核把关并提改进意见，最终输出一份可直接发布的周报。",
    objectiveTitle: "撰写本周科技圈深度周报",
    objectiveDescription:
      "面向科技行业关注者，输出一份本周深度周报。要求：\n" +
      "1. 运营主管：梳理本周值得关注的 3-5 个核心方向（如 AI 大模型、新硬件、产业动态等），明确每个方向的选题角度。\n" +
      "2. 内容编辑：按选题方向撰写每一项的精选解读（含背景、要点、影响），整体不少于 1500 字。\n" +
      "3. 质量审核：审查内容是否客观、引用是否准确、表达是否专业，列出待修改清单。\n" +
      "产出标准：可直接对外发布的周报正文 + 改进建议清单。",
    roles: [
      { id: "manager-1", role: "manager", label: "运营主管" },
      { id: "editor-1", role: "editor", label: "内容编辑" },
      { id: "reviewer-1", role: "reviewer", label: "质量审核" },
    ],
    maxTasks: 3,
    workers: 3,
    estimatedMinutes: 3,
  },
  {
    id: "product-research",
    iconName: "BarChart3",
    title: "产品调研报告团队",
    tagline: "调研 · 分析 · 编辑 · 审核 · 四角色深度协作",
    description:
      "调研员收集行业数据，分析师识别趋势与机会，编辑撰写正式调研报告，审核把关质量。展示更复杂的多角色协作和数据综合能力。",
    objectiveTitle: "撰写国内 AI Agent 平台市场调研报告",
    objectiveDescription:
      "为产品决策提供国内 AI Agent 平台市场调研。要求覆盖：\n" +
      "1. 调研员：盘点国内主流 AI Agent 平台（如字节扣子、百度千帆、阿里通义等），整理核心能力、定价、生态。\n" +
      "2. 分析师：基于调研数据分析市场格局、技术趋势、竞争差异，识别空白机会点。\n" +
      "3. 编辑：撰写正式调研报告，包含执行摘要、市场地图、趋势判断、机会建议四部分。\n" +
      "4. 审核：审查数据准确性、逻辑严谨性、结论可操作性。\n" +
      "产出标准：一份可呈交决策层的正式调研报告（不少于 2500 字）。",
    roles: [
      { id: "researcher-1", role: "researcher", label: "调研员" },
      { id: "analyst-1", role: "analyst", label: "分析师" },
      { id: "editor-1", role: "editor", label: "编辑" },
      { id: "reviewer-1", role: "reviewer", label: "审核" },
    ],
    maxTasks: 4,
    workers: 4,
    estimatedMinutes: 5,
  },
  {
    id: "hiring-evaluation",
    iconName: "Users",
    title: "招聘候选人评估团队",
    tagline: "HR · 面试官 · 评估委员 · 三角色决策协作",
    description:
      "HR 拆解岗位画像和评估维度，面试官按维度逐项评估候选人，评估委员综合判断给出录用建议。展示典型决策类业务场景。",
    objectiveTitle: "评估高级前端工程师候选人",
    objectiveDescription:
      "针对一位有 5 年经验的高级前端工程师候选人，给出综合录用建议。要求：\n" +
      "1. HR：拆解岗位核心画像（技术深度、协作能力、业务理解、文化匹配），列出 5-7 个具体评估维度和打分标准。\n" +
      "2. 面试官：按维度逐项评估候选人（基于其简历背景：5 年 React/TypeScript 经验、负责过百万 DAU 产品、有团队管理经验），给出每项分数和评估理由。\n" +
      "3. 评估委员：综合所有维度评分，给出最终录用建议（强烈推荐/推荐/有保留/不推荐），并说明关键判断依据和潜在风险。\n" +
      "产出标准：一份完整的候选人评估报告，含评分表、详细评估、最终建议。",
    roles: [
      { id: "manager-1", role: "manager", label: "HR" },
      { id: "analyst-1", role: "analyst", label: "面试官" },
      { id: "reviewer-1", role: "reviewer", label: "评估委员" },
    ],
    maxTasks: 3,
    workers: 3,
    estimatedMinutes: 3,
  },
];
