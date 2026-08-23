# Recording Agent Hub 使用手册

Recording Agent Hub 是一个 macOS 本地软件：录制软件完成录制后，它把最终视频交给你选定的 Agent 和该 Agent 的项目工作区。它不包含任何行业工作流或剪辑规则；规则、脚本和记忆属于你选择的 Agent 工作区。

## 1. 安装

1. 从 GitHub Releases 下载与你的 Mac 架构对应的 DMG 或 ZIP。
2. 将 `Recording Agent Hub.app` 移到“应用程序”。
3. 首次打开时，macOS 可能要求在 Finder 中右键应用并选择“打开”。
4. 打开软件后保持它运行。StreamCap 的完成回调需要它运行才能提交任务。

发布的 `.app` 不包含 Codex、Claude Code、Qoder 或 Kimi 的账号、CLI 和令牌。每台 Mac 都需要自行安装并登录要使用的 Agent。

## 2. 认识两个工作区

### Agent 项目工作区

这是 Agent 真正开始执行任务的目录。它可以包含项目说明、脚本、规则文件、`AGENTS.md`、技能和已有工具。例如，粗剪工作区应选择保存粗剪规则与脚本的项目目录。

### 任务工作区

每次录制自动创建一个内部任务目录，保存任务清单、提示词和日志。默认位置是：

```text
~/.recording-agent-hub/data/jobs/
```

任务工作区不是你需要手动选择的项目目录。

## 3. 配置 Agent 和工作区

1. 打开“自动化设置”。
2. 选择 Agent。
3. 点击“自动识别”。
4. 从下拉列表选择实际项目工作区，或点击“选择文件夹”。
5. 勾选“启用这个 Agent”。
6. 点击“保存设置”。

保存时，软件会自动建立一条“工作记忆”。它不需要导入：在“工作记忆”页选中某条记忆并点击“使用选中记忆”，即可一键恢复 Agent、工作区和启用状态。

### 自动识别说明

- Codex：从本机 Codex 会话记录读取真实使用过的 `cwd`，并显示 `Documents/Codex` 根目录与实际工作区。
- 其他 Agent：显示该 Agent 的常见项目根目录、已保存的工作记忆和当前工作区。
- 自动识别只提供候选目录，不读取或修改这些项目文件。

## 4. 连接 StreamCap

1. 在软件的“自动化设置”页复制“连接 StreamCap”命令。
2. 在 StreamCap 中启用“录制完成后执行自定义脚本”。
3. 将命令粘贴到“自定义脚本执行命令”。
4. 保持 Recording Agent Hub 在运行状态。

命令使用应用的 bundle identifier 启动回调，不包含当前用户名、视频目录、工作区路径或 Agent 名称。因此同一条命令可用于同一台 Mac 上切换不同 Agent，也可复制到另一台已安装同名应用的 Mac。真正使用哪个 Agent 由该 Mac 当前选中的工作记忆决定。

回调会等待最终文件连续 15 秒未变化后再提交。网络或应用暂时不可用时，回调会写入本机待发送队列；下次启动应用会自动重试。

## 5. 先做连通性测试

在“测试”页：

1. 选择一个视频样本。
2. 点击“测试触发”。
3. 在“任务”页查看状态。

测试任务只验证 Agent 能访问视频与项目工作区，不剪辑、转码、复制、删除或交付视频。成功日志会以 `TRIGGER_OK` 开头。

## 6. 运行、暂停、停止

- **暂停自动化**：保留软件和当前任务，但不领取新的队列任务。
- **继续自动化**：继续领取队列任务。
- **取消任务**：取消选中的队列任务；如果它正在运行，会请求终止对应 Agent 进程。
- **停止并退出**：停止本地回调服务并终止正在运行的 Agent。之后 StreamCap 的录制不会自动提交，直到再次打开软件。

## 7. Agent 前置条件

| Agent | 软件需要的本机条件 | 推荐认证方式 |
| --- | --- | --- |
| Codex | 安装并登录 `codex` CLI | Codex CLI 登录 |
| Claude Code | 安装并登录 `claude` CLI | Claude Code 登录或 `ANTHROPIC_API_KEY` |
| Qoder 国际版 | 安装 Qoder SDK | `QODER_PERSONAL_ACCESS_TOKEN` 由系统环境或密钥管理器提供 |
| Qoder 中国版 | 安装并登录 `qoderclicn` | Qoder 中国版 CLI 登录或 `QODERCN_PERSONAL_ACCESS_TOKEN` |
| Kimi Code | 安装并登录 `kimi` CLI | Kimi Code CLI 登录 |
| Hermes | 安装 `hermes` CLI | Hermes 自己的登录方式 |

软件不会要求你把令牌粘贴到界面，也不会将令牌写入工作记忆、配置、任务清单或日志。

## 8. 常见问题

### 提示端口 8787 被占用

说明另一份 Recording Agent Hub 或旧开发服务仍在运行。退出旧应用后再打开新应用。通常不需要修改 StreamCap 命令。

### Agent 状态显示“未找到 CLI/SDK”

在该 Mac 上安装并登录对应 CLI 后，重启应用或切换到“Agent 状态”页刷新。Finder 启动的应用不会继承终端的临时 `PATH`；软件会额外检查 `~/.local/bin` 中的 CLI。

### 录制完成后没有任务

确认：应用仍在运行；StreamCap 的完成回调已启用；选定 Agent 已启用；工作区仍存在；任务页没有错误信息。待提交回调保存在：

```text
~/.recording-agent-hub/pending-hooks/
```

### 成功但没有视频成品

默认任务要求输出目录有新建或更新的视频，并通过 `ffprobe` 校验。请检查所选 Agent 工作区内的规则、提示词、脚本和任务日志，确认 Agent 知道交付目录与成片条件。

## 9. 本机数据与清理

本机状态目录：

```text
~/.recording-agent-hub/
```

其中包括设置、工作记忆、任务数据库、日志和待提交回调。源视频保留在原始位置，不会被软件移动或删除。清理前先退出软件；删除整个目录会清除工作记忆与任务历史。
