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
    title: "科技周报编辑团队",
    tagline: "调研 · 撰稿 · 审核 — 三角色并行",
    description:
      "AI研究员梳理本周AI/硬件/产业三大方向的核心事件，主笔编辑整合为深度周报，审核员交叉核验数据和逻辑。Leader创建3个定制工人、4-5个并行任务，10分钟内看到完整产出。",
    objectiveTitle: "撰写本周科技产业深度周报",
    objectiveDescription:
      "面向科技行业从业者，撰写一份本周深度周报（不低于2000字），覆盖三个核心方向：\n\n" +
      "方向一：AI大模型领域本周最重要的2-3个进展（如新模型发布、开源动态、政策变化），每个进展需包含事件背景、技术要点、行业影响。\n" +
      "方向二：硬件与半导体本周动态（如新品发布、供应链变化、技术突破），需引用具体厂商和产品名称。\n" +
      "方向三：科技产业趋势（如投融资、监管政策、人才流动），需给出趋势判断和对从业者的影响分析。\n\n" +
      "产出标准：\n" +
      "- 每个方向单独成章节，小标题清晰，数据引用标注来源\n" +
      "- 整体语言专业但不晦涩，适合科技行业中层从业者阅读\n" +
      "- 最终由审核员交叉核验：事实是否准确、不同章节间数据是否自洽、是否存在遗漏重大事件",
    roles: [
      { id: "ai-researcher", role: "researcher", label: "AI研究员" },
      { id: "hardware-researcher", role: "researcher", label: "硬件研究员" },
      { id: "lead-editor", role: "editor", label: "主笔编辑" },
      { id: "content-reviewer", role: "reviewer", label: "内容审核" },
    ],
    maxTasks: 5,
    workers: 4,
    estimatedMinutes: 8,
  },
  {
    id: "product-research",
    iconName: "BarChart3",
    title: "市场调研分析团队",
    tagline: "调研 · 分析 · 撰写 · 审核 — 四角色流水线",
    description:
      "数据调研员收集平台数据和定价信息，商业分析师判断市场格局和机会点，报告编辑撰写正式调研文档，质量审核把关准确性和逻辑。适合展示复杂信息综合能力。",
    objectiveTitle: "国内AI Agent开发平台市场调研报告",
    objectiveDescription:
      "为产品团队选型决策提供一份完整的国内AI Agent开发平台市场调研报告。需覆盖以下内容：\n\n" +
      "1. 平台盘点：至少覆盖5个主流平台——字节扣子(Coze)、百度千帆AppBuilder、阿里百炼、Dify(开源)、腾讯元器。每个平台记录：核心能力（是否支持RAG/工作流/插件/多Agent）、定价模式（免费额度/付费阶梯）、主要客户案例、API开放程度。\n" +
      "2. 横向对比：从开发者体验（上手难度/文档质量/社区活跃度）、企业级能力（权限管理/审计/私有部署）、生态兼容性（模型支持/数据源接入/飞书集成）三个维度做对比矩阵。\n" +
      "3. 市场判断：识别当前市场空白（哪些场景没有被很好覆盖），给出2-3个具体的产品机会建议。\n\n" +
      "产出标准：2500字以上的正式调研报告，含对比表格、市场地图、选型建议。数据需要标注来源（官方文档/第三方评测/社区反馈），无法确定的信息需标注为「推测」。",
    roles: [
      { id: "data-researcher", role: "researcher", label: "数据调研员" },
      { id: "business-analyst", role: "analyst", label: "商业分析师" },
      { id: "report-editor", role: "editor", label: "报告编辑" },
      { id: "quality-reviewer", role: "reviewer", label: "质量审核" },
    ],
    maxTasks: 5,
    workers: 4,
    estimatedMinutes: 10,
  },
  {
    id: "hiring-evaluation",
    iconName: "Users",
    title: "候选人综合评估团队",
    tagline: "画像 · 评估 · 整合 — 三角色决策",
    description:
      "HR拆解岗位画像和打分维度，技术面试官逐项评估候选人能力，综合评委汇总给出录用建议和风险提示。典型的多维度评估决策类场景。",
    objectiveTitle: "高级前端工程师候选人综合评估",
    objectiveDescription:
      "针对一位候选人给出结构化录用评估报告。候选人背景：5年前端经验，React/TypeScript技术栈，曾主导百万DAU产品的架构升级，近一年带领3人前端小组。\n\n" +
      "1. 岗位画像拆解：从技术深度（React生态/性能优化/工程化）、架构能力（系统设计/跨端方案）、协作与领导力（代码评审/跨部门沟通/团队管理）、业务理解（如何用技术支撑业务目标）、文化匹配（是否适应快节奏/数据驱动/开源文化）五个维度建立评估框架，每个维度给出1-5分的打分标准。\n" +
      "2. 逐项评估：基于候选人简历和背景，对每个维度给出具体评估——做了什么（引用简历细节）、达到了什么水平（对应打分标准）、有什么不足（需要入职后补强的部分）。\n" +
      "3. 综合结论：给出五档推荐（强烈推荐/推荐/有保留推荐/不建议/强烈不建议），说明核心理由，列出录用后的前3个月培训重点和潜在风险（如是否适应团队风格、技术栈匹配度）。\n\n" +
      "产出标准：完整的结构化评估报告，含评分矩阵、逐项评估详述、综合结论和培养建议。所有结论必须有具体依据支撑，不可空泛。",
    roles: [
      { id: "hr-profiler", role: "analyst", label: "HR画像分析师" },
      { id: "tech-interviewer", role: "researcher", label: "技术面试官" },
      { id: "final-evaluator", role: "reviewer", label: "综合评委" },
    ],
    maxTasks: 4,
    workers: 3,
    estimatedMinutes: 8,
  },
];
