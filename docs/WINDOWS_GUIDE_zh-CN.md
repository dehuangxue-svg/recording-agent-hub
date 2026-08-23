# Recording Agent Hub Windows 使用手册

Windows 版与 macOS 版的工作方式相同：StreamCap 完成录制后调用本机回调，Recording Agent Hub 再把最终文件交给选定的 Agent 和项目工作区。

## 1. 安装

1. 从 GitHub Releases 下载 `Recording-Agent-Hub-Windows-x64-Setup.exe`。不能安装软件的电脑可以下载便携版 ZIP。
2. 运行安装程序，然后从开始菜单打开 **Recording Agent Hub**。
3. 如果 Windows SmartScreen 提示这是未签名的社区版本，请先确认文件来自本仓库，再选择“更多信息 -> 仍要运行”。
4. StreamCap 完成录制时，需要保持本软件正在运行。

安装程序只为当前用户安装，不需要管理员权限。本机设置、工作区记忆、任务和日志保存在：

```text
%USERPROFILE%\.recording-agent-hub\
```

## 2. 安装运行依赖

先安装 FFmpeg，并在 PowerShell 中确认以下命令可用：

```powershell
ffprobe -version
```

然后安装并登录需要使用的 Agent CLI。安装包包含 Qoder SDK 适配器，但不包含 Agent 账号和令牌。安装新的 CLI 后需要重启 Recording Agent Hub，让软件重新识别 Windows 可执行文件路径。

软件会自动检查 `%APPDATA%\npm`、`%LOCALAPPDATA%\Microsoft\WindowsApps`、`%USERPROFILE%\.local\bin` 和 Scoop shims 等常见目录。

## 3. 选择 Agent 工作区

1. 打开“自动化设置”。
2. 选择 Agent。
3. 点击“自动识别”，选择真正包含该 Agent 规则和脚本的项目工作区；列表中没有时点击“选择文件夹”。
4. 启用 Agent，然后点击“保存设置”。

保存后会自动出现在“工作区记忆”中，以后可以直接点击使用，不需要导入 JSON 文件。

## 4. 连接 StreamCap

1. 复制软件“连接 StreamCap”区域显示的命令。
2. 在 StreamCap 中启用录制完成后执行自定义脚本。
3. 原样粘贴命令，不要删除可执行文件路径两侧的引号。

Windows 命令会记录当前电脑上的实际安装路径。如果另一台电脑的安装目录不同，应当在那台电脑的软件中重新生成命令，不要直接复制旧电脑的命令。

## 5. 先做不剪辑测试

在“测试”页选择一个样本视频并运行“测试触发”。测试只确认 Agent 可以访问视频和项目工作区，不允许剪辑、转码、复制或生成成品。成功结果以 `TRIGGER_OK` 开头。

## 6. 暂停、取消和停止

- “暂停自动化”只是不再领取新的排队任务，软件仍然运行。
- “取消任务”会取消选中的任务，并终止该 Agent 的整个进程树。
- “停止并退出”会停止回调服务，并终止正在运行的 Agent 进程树。

## 7. 常见问题

### 找不到 Agent 或 ffprobe

先在新打开的 PowerShell 中确认对应命令可以运行，然后重启 Recording Agent Hub。只在某一个终端临时设置的 `PATH`，已经运行的桌面软件无法读取。

### 8787 端口被占用

关闭另一份 Recording Agent Hub 或旧的开发服务，然后重新打开软件。

### StreamCap 完成后没有任务

确认软件仍在运行、StreamCap 回调命令已启用、选定 Agent 已启用、项目工作区仍然存在。提交失败的回调会保存在 `%USERPROFILE%\.recording-agent-hub\pending-hooks\`，软件下次启动时会重试。

### Qoder 认证

请通过用户环境变量或凭据启动器在软件配置之外设置 `QODER_PERSONAL_ACCESS_TOKEN`，修改环境变量后重启软件。不要把令牌写入 Issue、工作区记忆、任务提示或 Git 提交。

## 8. 从源码构建

安装 Python 3.10+、`uv`，并可选安装 Inno Setup 6，然后在 PowerShell 中运行：

```powershell
uv sync
uv run python -m unittest discover -s tests -v
.\scripts\build_windows.ps1
```

便携版 ZIP 和安装程序会生成在 `dist\`。PyInstaller 不能在 macOS 上生成可靠的 Windows EXE，因此公开下载文件由 GitHub Actions 的真实 Windows 环境构建。
