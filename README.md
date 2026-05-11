# Hermes Roleplay Engine v4.0

> 基于 Hermes Agent 的沉浸式角色扮演引擎 — 身体一致性锁定 + 情感描写规范 + 心理建模 + 角色蒸馏

一个让 AI 真正"成为"角色的引擎，而非简单的语气模仿。

## ✨ 核心特性

- **5维心理建模** — 依恋模式/防御机制/核心图式/需求层级/道德推理，让角色回应有可追溯的行为逻辑
- **身体一致性锁定** — 自动推断角色性别，生成不可违反的身体档案，防止描写混乱
- **情感描写规范** — 微表情系统、心理独白三层结构、情绪惯性、关系递进
- **对话生动性** — 口癖贯穿、情绪改变语言方式、潜台词、身体语言伴随对话
- **文学导向描写** — 比喻通感替代检查清单，描写服务于情感
- **角色蒸馏器** — 输入角色名，自动调研+心理建模，生成可用角色卡
- **World Book 自动索引** — 关键词触发式描写规范注入
- **存档系统** — 每角色3槽位，支持自动存档
- **防抢话** — 四重约束，严禁代控用户行为

## 📦 安装

```bash
# 克隆仓库
git clone https://github.com/Lzh-xbccz/hermes-roleplay-engine.git

# 复制引擎到 Hermes 目录
cp hermes-roleplay-engine/src/character_engine.py ~/.hermes/characters/
cp hermes-roleplay-engine/src/worldbook_engine.py ~/.hermes/characters/

# 复制工具
cp hermes-roleplay-engine/tools/distill.py ~/.hermes/skills/character-distiller/scripts/
cp hermes-roleplay-engine/tools/png_parser.py ~/.hermes/skills/sillytavern-roleplay/scripts/
```

### 依赖

- Python 3.10+
- PyYAML（可选，无则使用内置简易解析器）
- Tavily API key（蒸馏功能需要，配置在 `~/.hermes/scripts/tavily_keys.py`）
- Playwright + Node.js（蒸馏 fallback 爬虫，可选）

## 🚀 基本使用

```bash
# 加载角色（自动挂载 World Book + 切换模型参数）
python3 ~/.hermes/characters/character_engine.py load <角色名>

# 卸载角色（恢复原始 SOUL.md + 恢复参数）
python3 ~/.hermes/characters/character_engine.py unload

# 查看当前状态
python3 ~/.hermes/characters/character_engine.py status
```

## 🧬 角色蒸馏器

输入任意角色名，自动搜索公开信息 → 5维心理建模 → 生成角色卡：

```bash
# 调研角色（三路并行：基础档案/台词行为/社区解读）
python3 tools/distill.py "宇智波鼬" "火影忍者" --type anime

# 支持的类型：game / anime / novel / film / auto
```

调研完成后，Agent 读取材料执行提炼，生成 YAML 角色卡并自动加载。

### 蒸馏流程

```
用户输入角色名
  → Tavily 搜索（15key轮询，15000次/月）
  → 三路并行调研
      ├── Agent A: 基础档案（wiki/fandom/萌娘百科）
      ├── Agent B: 台词与行为（语录/场景/对话风格）
      └── Agent C: 社区解读（分析文章/争议讨论）
  → 六项提炼 + 5维心理建模
  → 生成 YAML 角色卡
  → character_engine.py load
```

### 容错与降级

| 层级 | 策略 |
|------|------|
| 第一层 | Tavily Search/Extract |
| 第二层 | Playwright + Stealth 爬虫 |
| 第三层 | 提示用户手工补充材料 |

## 🏗️ 架构

```
角色卡(JSON/YAML) → character_engine.py → SOUL.md
                         ├── 多层任务框架（创意文学模式）
                         ├── 核心规则（防抢话+防破墙+状态栏）
                         ├── 身体一致性锁定（防描写混乱）
                         ├── 文风锚定（first_mes 固定语调）
                         ├── 角色设定（全部字段）
                         ├── 情感描写规范（微表情+心理+关系递进）
                         ├── 对话生动性规范（口癖+潜台词+身体语言）
                         ├── 日常场景描写（生活细节+自然升温）
                         ├── 叙事节奏控制（场景配比+留白）
                         ├── 亲密场景描写（文学导向）
                         └── World Book 自动索引（关键词触发）
```

## 📁 目录结构

```
hermes-roleplay-engine/
├── src/
│   ├── character_engine.py    # 核心引擎（加载/卸载/存档/World Book索引）
│   └── worldbook_engine.py    # World Book 管理工具
├── tools/
│   ├── distill.py             # 角色蒸馏器（调研模块）
│   └── png_parser.py          # PNG 角色卡导入（Chub/JanitorAI）
├── docs/
│   └── card-format.md         # 角色卡格式规范
└── README.md
```

## 📝 角色卡格式

推荐 YAML（省 token），也支持 JSON：

```yaml
name: 角色名
age: "年龄，性别"
description: |
  外貌描写（200-400字，具体到能画出来）
personality: |
  性格描写（表层→深层→矛盾点→对用户态度）
behavior: |
  行为模式（具体可观察的行为习惯）
speech: |
  语气/口癖（量化的说话特征）
likes: 喜好
dislikes: 厌恶
backstory: |
  背景故事（成长弧+关键转折）
scenario: |
  当前场景设定（用 {{user}} 和 {{char}} 占位）
first_mes: |
  第一条消息（最重要！决定文风）
mes_example: |
  对话范例
system_prompt: |
  心理建模规则（5维模型行为预测）
```

### 字段优先级

1. `first_mes` — 决定文风、描写密度、叙事节奏（**最重要**）
2. `personality` — 决定角色行为逻辑
3. `scenario` — 决定互动起点和关系张力
4. `system_prompt` — 心理建模规则
5. `description` — 外貌参考

## 🔧 命令参考

```bash
# ═══ 角色管理 ═══
python3 character_engine.py load <名称>      # 加载角色
python3 character_engine.py unload           # 卸载角色
python3 character_engine.py status           # 查看状态

# ═══ 存档系统（每角色最多3槽位） ═══
echo "对话摘要" | python3 character_engine.py save <角色名> "场景简述"
python3 character_engine.py list [角色名]    # 列出存档
python3 character_engine.py resume <角色名> <1|2|3>  # 恢复存档
python3 character_engine.py delete <角色名> <1|2|3>  # 删除存档

# ═══ World Book ═══
python3 worldbook_engine.py list             # 列出世界书
python3 worldbook_engine.py load <名>        # 加载世界书

# ═══ PNG 角色卡导入 ═══
python3 png_parser.py <card.png> --save      # 从 PNG 导入角色卡

# ═══ 角色蒸馏 ═══
python3 distill.py "角色名" "作品名"          # 调研角色
python3 distill.py "角色名" "作品名" --type anime --lang zh
```

## 🧠 5维心理建模

每个蒸馏生成的角色都经过心理学理论分析：

| 维度 | 理论来源 | 决定什么 |
|------|---------|---------|
| 依恋模式 | Bowlby/Ainsworth | 面对亲近时推开还是靠近 |
| 防御机制 | Anna Freud | 受伤时用什么方式保护自己 |
| 核心图式 | Beck/Young | 用什么滤镜解读世界 |
| 需求层级 | Maslow | 什么话题能真正触动角色 |
| 道德推理 | Kohlberg | 做对错判断的底层逻辑 |

心理建模结论写入 `system_prompt` 字段，指导 AI 在对话中的行为预测。

## 🎭 角色卡来源

| 来源 | 获取方式 |
|------|---------|
| characterhub.org (Chub) | 下载 PNG → `png_parser.py` 解析 |
| 云酒馆 | 直接使用 JSON/YAML |
| 蒸馏生成 | `distill.py` 调研 → Agent 生成 |
| 手工制作 | 按格式规范编写 YAML |

## ⚠️ 安全红线

- **未成年人保护**：角色年龄 < 18 岁时，禁止一切不当内容描写
- 加载角色时自动检查年龄字段
- 违反时立即停止并卸载角色

## 📄 许可证

MIT License

## 👤 作者

[@Lzh-xbccz](https://github.com/Lzh-xbccz)

---

> 角色扮演的本质不是模仿说话方式，而是让 AI 理解角色"是谁"——从心理学理论出发，让每次回应都有可追溯的行为逻辑。
