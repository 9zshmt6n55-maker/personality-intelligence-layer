# 人格智能层

PIL，全称 Personality Intelligence Layer，意思是“人格智能层”。

这个项目的目标不是保存一大堆上下文，也不是写一个简单的角色设定文件。它想做的是：给每个 AI 代理建立一个可以成长、可以迁移、可以继续发展的行为内核。

一句话：

```text
过去的原始细节可以忘记。
但过去塑造出来的行事风格应该留下来。
```

## 这个项目解决什么问题

现在很多 AI 代理靠三种东西维持连续性：

- 很长的上下文
- 记忆文件
- 固定角色提示词

这些东西有用，但它们不等于真正稳定的人格层。

一个长期代理真正需要的是：即使上下文丢失、新开对话、换环境，也能保留自己的判断方式、做事习惯、风险意识、和用户之间形成的配合方式。

PIL 做的就是这个中间层。

## 为什么这个方向有价值

PIL 的核心优势不是“记得更多”，而是“沉淀得更干净”。

- **不依赖长上下文**：不用每次把过去聊天全部塞回模型。
- **不是普通记忆文件**：它保存的不是流水账，而是性格、偏好、边界、纠错规则、决策倾向。
- **每个代理独立成长**：一个 profile 对应一个代理，多个代理可以同时存在，不互相覆盖。
- **老代理可以迁移**：老代理可以生成 `PIL_PERSONALITY_BACKUP.md`，新对话读取后恢复原来的行事风格。
- **状态可见**：人格球和观察台能看到人格域、成长、变化，而不是黑箱。
- **行为由多股力量合成**：谨慎、直接、自主、信任、边界、好奇、风险敏感等信号共同影响行动。
- **允许合理遗忘**：不追求保存所有细节，而是把经历压缩成人格变化。
- **既能当协议，也能当程序跑**：没有桌面环境时，Markdown 文件仍然能指导代理恢复；有 Python 环境时，可以生成人格球和状态文件。

这不是最终形态，而是一个清晰的开源原型：人格状态、代理 profile、行为仲裁、可见成长、跨会话恢复。

## 普通用户怎么用

先进入项目文件夹：

```powershell
cd <PIL_ROOT>
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

### 让代理按人格层做一次决策

```powershell
python .\pkm_runtime.py decide --profile test-agent "用户要求马上给出一个高风险方案。"
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

- `agent.pkm.json`：这个代理的人格智能层状态。
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
- 行动是多信号仲裁结果。
- 过去可以被压缩为变化。
- 每个代理有独立身份边界。
- 用户能看到人格层如何变化。
