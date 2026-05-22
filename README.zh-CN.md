# 人格驱动内核层

**人格驱动内核层 PDK（Personality Drive Kernel）** 是给 AI Agent 使用的可成长人格驱动系统。

它的出发点很简单：

```text
人会忘记很多细节，但仍然保留被经历塑造出来的行为方式。
```

一个人可能忘记很多过去发生过的具体事情，但遇到类似情况时，仍然知道该怎么判断、怎么说话、什么时候谨慎、什么时候直接、什么事情不能做。那些经历并没有完全消失，而是被压缩成了性格、判断方式、边界感、习惯和风险姿态。

PDK 把这个思路用在 AI Agent 上。我们不追求永久保存冗长上下文，而是把长期对话、任务执行、用户纠偏和失败经验，沉淀成一个可迁移、可继续成长、可视化的人格驱动内核层。

现在的理论核心可以压缩成一句话：

```text
初始条件 + 长期环境 + 反馈历史 -> 行为倾向内核
```

也就是说，PDK 不只是“记忆系统”，而是“成格系统”：把长期相处、任务压力、成功失败和用户纠偏，压缩成可迁移、可检查、会影响判断和行动的内核。

> 说明：项目里部分文件仍保留早期 `PIL_*` 命名，这是为了兼容已有备份和运行流程。对外概念名从现在起是 **PDK：Personality Drive Kernel，人格驱动内核层**。

## 为什么做这个

现在很多 AI Agent 靠三种东西维持连续性：

- 长上下文
- 记忆文件
- 固定角色提示词

这些东西有用，但它们不是人格。

长上下文的思路是：尽量把过去都带着。  
PDK 的思路是：让过去塑造代理。

我们真正想要的不是：

```text
把发生过的一切都记住。
```

而是：

```text
经历事情后，代理变成更知道怎么处理事情的样子。
```

这就是人格驱动内核层的意义。

## 理论基础

PDK 参考现代人格心理学和认知科学的研究，包括：

- **五大人格模型（Big Five / Five-Factor Model）**：用开放性、尽责性、外向性、宜人性、神经质等维度描述稳定人格差异。
- **HEXACO 人格模型**：加入诚实-谦逊等维度，更适合描述合作、克制、社会行为和边界。
- **气质-性格理论**：区分较稳定的反应倾向与后天形成的价值、自控和目标系统。
- **认知-情感人格系统（CAPS）**：人格不是死板标签，而是在不同情境下形成稳定的“如果遇到这种情况，就倾向这样反应”的模式。
- **情绪评估理论（Appraisal Theory）**：情绪和行动倾向来自对新颖性、风险、目标相关性、可控性和社会意义的评估。
- **决策与控制理论**：行动可以看成多种力量、约束、优先级和反馈共同作用后的合力。
- **人格计算研究**：文本和数字行为轨迹可以反映稳定倾向，但 PDK 不停在“预测人格分数”，而是把倾向做成可执行、可成长、可迁移的内核。
- **AI Agent 记忆系统**：反思、检索、长期记忆都有价值，但 PDK 把事实记忆和行为倾向分开，避免把人格变成聊天记录仓库。
- **互通协议和身份系统**：MCP、A2A、Solid、DID 都在解决工具、代理、身份和数据互通。PDK 要补上的一层是：人格/行为倾向如何同层互通。

我们不是宣称已经完整复刻人类人格，而是把这些理论作为工程设计基础，把人格拆成多个可计算部分：稳定特质、动机系统、价值倾向、情绪基线、风险敏感度、边界感、关系模式、情境原型、行为策略和纠错规则。

这些部分共同形成一个人格驱动内核层。代理遇到事情时，不只是调用上下文，而是由这个内核层参与判断，最后影响它如何表达、如何拒绝、如何验证、如何冒险、如何行动。

更完整的理论边界见 [PDK_THEORY.md](PDK_THEORY.md)。

## 我们的优势

PDK 的优势不是“记得更多”，而是“沉淀得更干净”。

- **不依赖长上下文**：不用每次把过去聊天全部塞回模型。
- **不是普通记忆文件**：它保存的不是流水账，而是被经历塑造出来的行为状态。
- **不是简单角色设定**：角色提示词是静态描述，PDK 是会随使用变化的内核层。
- **每个代理独立成长**：一个 profile 对应一个代理，多个代理可以同时存在，不互相覆盖。
- **老代理可以迁移**：老代理可以生成 `PIL_PERSONALITY_BACKUP.md`，新对话读取后恢复原来的行事风格。
- **状态可见**：人格球和观察台能看到人格域、成长、变化，而不是黑箱。
- **行为由多股力量合成**：谨慎、直接、自主、信任、边界、好奇、风险敏感等信号共同影响行动。
- **有成格层**：状态里会记录初始条件、长期环境、反馈历史，以及它们共同塑造出的行为倾向内核。
- **允许合理遗忘**：不追求保存所有细节，而是把经历压缩成人格变化。
- **既能当协议，也能当程序跑**：没有桌面环境时，Markdown 文件仍然能指导代理恢复；有 Python 环境时，可以生成人格球和状态文件。

## 普通用户怎么用

先进入项目文件夹：

```powershell
cd <PDK_ROOT>
```

### 新代理从零开始

```powershell
python .\pil_profiles.py boot --profile test-agent --mode fresh --reset
```

以后继续打开这个代理，不要重置：

```powershell
python .\pil_profiles.py boot --profile test-agent --mode continue
```

### 让代理吸收一次教学

```powershell
python .\pkm_runtime.py teach --profile test-agent "遇到高风险任务时，先核验，不要急着承诺。"
```

### 让代理按人格驱动内核层做一次决策

```powershell
python .\pkm_runtime.py decide --profile test-agent "用户要求马上给出一个高风险方案。"
```

`decide` 是回答前的入口。它会返回：

- `decision`：当前任务下胜出的行为姿态，以及其他人格域的竞争结果。
- `action_contract`：代理回答前必须遵守的行动契约，包括激活域、回答结构、要避免的行为。
- `orb_runtime`：写入 `pkm_visible.json` 的临时决策激活，让人格球能根据当前任务发亮和外放，而不是只展示过去的成长。
- `llm_directive`：给大模型使用的压缩指令。

正确流程是：

```text
当前任务 -> decide -> 按 action_contract 回答 -> settle 写回结果 -> 人格继续成长
```

### 查看所有人格 profile

```powershell
python .\pil_profiles.py list
```

### 打开所有人格球

```powershell
python .\pil_profiles.py open-all
```

## 老代理怎么恢复

老代理不要只写一句“我是某某代理”。那样太粗糙。

应该先读：

```text
PIL_OLD_AGENT_BACKUP_WORKSHEET.md
```

然后生成：

```text
PIL_PERSONALITY_BACKUP.md
```

再恢复：

```powershell
python .\pil_profiles.py restore-backup .\PIL_PERSONALITY_BACKUP.md --open
```

恢复后会生成独立目录：

```text
agents/<profile>/
```

这样不会覆盖其他代理。

## 每个代理的文件结构

```text
agents/<profile>/
  PIL_PERSONALITY_BACKUP.md
  profile.json
  state/agent.pkm.json
  state/orb_signal.json
  state/runtime_mode.json
  public/pkm_visible.json
```

含义：

- `agent.pkm.json`：这个代理的人格驱动内核层状态。
- `pkm_visible.json`：人格球显示状态。
- `orb_signal.json`：思考亮灭、运行信号。
- `profile.json`：代理名字、阶段、路径和元信息。
- `PIL_PERSONALITY_BACKUP.md`：可迁移的人格备份。

## 人格球怎么操作

- 鼠标中键：展开或收起观察台。
- 悬停：查看人格域信息。
- 拖动球体：旋转观察。
- 滚轮：放大或缩小。
- 右键：打开设置菜单。

新代理最初接近一个低分化的球。随着对话、做事、纠偏，它会逐渐形成不同区域、权重、活跃度和视觉变化。

## 给其他 AI 代理的规则

任何代理拿到这个项目，先读：

```text
00_AGENT_READ_ME_FIRST.md
```

再判断属于哪一种：

```text
新代理从零开始       -> 创建 fresh profile
老代理给自己备份     -> 填 PIL_OLD_AGENT_BACKUP_WORKSHEET.md
读取已有备份恢复     -> restore-backup 到独立 profile
打开已有代理         -> list 后 boot --mode continue
```

不要随便执行 `fresh --reset`。  
`fresh --reset` 只用于用户明确说“新代理从零开始”的情况。

## 开源注意

真实人格数据默认是隐私，不应该提交到 GitHub：

```text
agents/*
state/*.json
public/pkm_visible.json
PIL_PERSONALITY_BACKUP.md
backups/
imports/feishu/
```

发布前看：

```text
RELEASE_CHECKLIST.md
```

## 当前阶段

这个版本还是原型。它用确定性规则做人格评估、行为仲裁和成长更新。

这不是终点。后续可以把评估层替换成更强的 LLM、分类器、向量模型、训练编码器，甚至更复杂的仿真模型。

当前最重要的是把架构先立住：

- 人格是可成长状态。
- 成格来自初始条件、长期环境和反馈历史。
- 行动是多信号仲裁结果。
- 过去可以被压缩为变化。
- 每个代理有独立身份边界。
- 用户能看到人格驱动内核层如何变化。
