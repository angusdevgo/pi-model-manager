# ⚡ Pi Model Manager (Pi 模型与服务商配置管理器)

<p align="center">
  <a href="#-中文说明">中文说明</a> | <a href="#-english">English</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Platform-Windows-0078D6?style=flat-square&logo=windows&logoColor=white" alt="Platform">
  <img src="https://img.shields.io/badge/Pi--Agent-v0.84+-lightgrey?style=flat-square" alt="Pi Agent Version">
  <img src="https://img.shields.io/badge/License-MIT-green.svg?style=flat-square" alt="License">
</p>

---

<a id="-中文说明"></a>

## 🇨🇳 中文说明

### ⚡ 工具背景

在 `Pi-Coding-Agent` 中引入自定义大模型服务商（如本地私有部署的 **Ollama**、**LM Studio**，或者云端的 **DeepSeek**、**OpenRouter**、**MiniMax** 等）以往只能通过手动编辑 JSON 配置文件 (`models.json`)。这带来了以下痛点：
1.  **极易写错格式**：少写一个逗号或引号都会导致解析失败，令 Agent 报错无法运行。
2.  **流程繁琐**：每次增删模型、修改 API 密钥或修改 URL，都需要查阅文档字段并手动打字编辑，且修改后需要重启 Pi 会话。
3.  **盲目添加与无法测活**：拉取到一大堆模型后，不知道哪些真实可用、哪些由于网络或 Key 权限问题无法接通。
4.  **缓存冲突与覆盖**：内置的提供商目录或本地远程目录缓存经常会覆盖自定义的设置，使得已删除的模型在列表中复活。

**Pi 模型管理器** 提供了一个纯本地的图形化窗口，安全地读写 `models.json`。它支持自动识别 Agent 配置路径、缓冲式拉取服务商模型、模型一键测活（可用性检测）、随时修改模型别名、智能合并高级参数（如 `compat` 兼容标志、输入输出计费 `cost`、上下文窗口大小 `contextWindow` 等），并自带扩展，实现保存即生效的免重启同步。

---

### ✨ 核心功能特性

*   🖥️ **原生桌面客户端**：纯本地运行，采用现代磨砂玻璃/无边框设计风格，体验丝滑（无需开启本地网页服务器或打开浏览器）。
*   📦 **服务商管理 (CRUD)**：
    *   可视化新增、编辑、删除模型服务商。
    *   **实时搜索过滤**：支持在左侧列表按 ID 或名称快速筛选服务商。
    *   **彩色协议徽章**：清晰标明 `OpenAI`、`Claude`、`Gemini`、`Resp` 等协议类型。
    *   **API Key 明文切换**：支持 `👁️ / 🙈` 一键显隐密码，方便核对密钥。
*   🤖 **模型管理与别名**：
    *   **📥 缓冲式拉取预览**：点击「自动拉取模型」后进入预览面板，不会直接覆盖列表，可勾选目标模型后批量导入。
    *   **✏️ 随时修改别名**：拉取预览时、手动添加时、以及已在列表中的模型，均可**直接点击编辑别名**，回车或失焦自动保存。
    *   **🔍 模型实时过滤**：已添加列表和拉取预览区均支持实时关键词过滤。
*   ⚡ **模型测活 (Connectivity Test)**：
    *   **单模型测活**：每个模型标签右侧均有 ⚡ 按钮，发送最小化请求真实验证 API 是否通畅。
    *   **批量测活**：拉取预览区支持「⚡ 全部测活」，一键并发检测所有拉取模型的连通性与响应耗时。
    *   **直观状态指示**：成功显示绿色 ✓ 及毫秒耗时（如 `可用 · 185ms`），失败显示红色 ✗ 及具体 HTTP 状态码/错误原因。
*   🔄 **热更新与同步 (Live Sync)**：搭配配套 Pi 扩展，在保存配置后自动热更新当前正在运行的 Pi 终端模型列表，**无需重启，也无需执行 `/reload`**。
*   ⌨️ **快捷键支持**：支持全局 <kbd>Ctrl + S</kbd> 一键保存配置。
*   🔒 **字段保护与合并**：保存时自动清理无效的空字段，并智能合并现有 `models.json` 中的高级配置（如 `compat`、`cost`、`contextWindow` 等），避免丢失手动调优的参数。
*   🚀 **一键启动**：支持在管理器中一键启动一个新的 Pi 交互式会话终端。

---

### 🚀 快速开始

#### 1. 安装依赖
本项目需要 Python 3.9+ 环境。在运行前请先安装 `pywebview`：
```bash
pip install pywebview
```

#### 2. 下载并运行
*   **方法 A**：双击目录下的 `PiModelManager.bat` 启动管理器（或者双击桌面的 `PiModelManager` 快捷方式）。
*   **方法 B**：直接通过命令行启动：
    ```bash
    pythonw.exe desktop_app.py
    ```

---

### 🔄 实现免重启热同步 (Live Sync)

为了在修改配置后让正在运行的 Pi 会话立刻生效，本项目附带了一个 Pi 扩展 `models-sync.ts`。

#### 安装步骤：
1.  将本项目中的 `models-sync.ts` 复制到你的 Pi 全局扩展目录中：
    *   **Windows 路径**: `%USERPROFILE%\.pi\agent\extensions\models-sync.ts`
2.  在已打开的 Pi 终端中执行一次 `/reload` 以加载此扩展（之后就不再需要手动 reload 了）。
3.  扩展加载后，它会在后台监听 `models.json` 的修改。每当你在桌面管理器中点击 **💾 保存**（或按 `Ctrl+S`），Pi 终端会立刻同步，并弹出通知：
    > `[info] 已同步 models.json（5 个服务商 / 16 个可用模型）`
4.  你也可以在 Pi 终端中输入 `/sync-models` 手动触发同步。

---

### 📂 文件目录说明

```text
pi-model-manager/
├── desktop_app.py      # 桌面客户端主程序 (Pywebview + HTML5/CSS3/JS)
├── models-sync.ts      # Pi 终端的配套同步扩展脚本
├── PiModelManager.bat  # 用于后台启动应用的 Windows 批处理脚本
├── README.md           # 中英双语说明文档
└── .gitignore          # Git 忽略配置
```

---

<a id="-english"></a>

## 🌐 English

### ⚡ Introduction

Adding custom model providers (e.g., local **Ollama**, **LM Studio**, or remote **DeepSeek**, **OpenRouter**, **MiniMax**) to `Pi-Coding-Agent` used to require manually editing the JSON configuration file (`models.json`). This workflow was prone to errors:
1. **Syntax Sensitivity**: A single missing comma or quote could break the agent startup.
2. **Tedious Process**: Users had to look up configuration options, edit JSON manually, and restart the CLI session or run `/reload` to sync.
3. **Unverified Models**: After fetching dozens of models, there was no way to verify whether each model actually connects or is accessible with the given API key.
4. **Registry Conflicts**: Cached remote directories and built-in overrides often merged unexpectedly, keeping deleted models active.

**Pi Model Manager** is a lightweight, local graphical desktop tool designed to manage custom providers and models safely. It features automatic config path discovery, buffered model fetching, one-click connectivity testing (model health checks), inline model aliases, smart merging of advanced configs (`compat`, `cost`, `contextWindow`), and a companion hot-reload extension.

---

### ✨ Features

*   🖥️ **Native Desktop GUI**: Built using `pywebview`, providing a modern frosted-glass dark theme interface without starting local servers.
*   📦 **Provider Management (CRUD)**:
    *   Visually add, edit, or delete custom providers.
    *   **Live Search**: Filter providers in real-time by ID or display name.
    *   **Protocol Badges**: Clear badges for `OpenAI`, `Claude`, `Gemini`, `Resp` protocols.
    *   **Password Toggle**: Show/hide API keys with `👁️ / 🙈`.
*   🤖 **Model Management & Custom Aliases**:
    *   **📥 Buffered Fetching**: Models fetched via `/v1/models` enter a staging preview pane, allowing you to select and configure aliases before importing.
    *   **✏️ Inline Alias Editing**: Directly edit display names/aliases anywhere (in the staged preview, on manual add, or on existing tags) with auto-save on blur/Enter.
    *   **🔍 Instant Filter**: Filter added models or fetched preview items by keyword.
*   ⚡ **Model Connectivity Testing (Health Check)**:
    *   **Single Model Test**: Click the ⚡ button next to any model to send a minimal payload and verify endpoint connectivity.
    *   **Batch Test**: Run "⚡ Test All" in the preview pane to check all fetched models concurrently.
    *   **Live Status**: Displays response latency in milliseconds (e.g., `Available · 185ms`) or detailed HTTP error codes upon failure.
*   🔄 **Zero-Restart Sync (Live Sync)**: Automatically hot-updates models in your active Pi session on save using a background file watcher.
*   ⌨️ **Keyboard Shortcut**: Press <kbd>Ctrl + S</kbd> anywhere in the window to save configuration.
*   🔒 **Safe Merging**: Cleans empty optional values and preserves advanced handwritten flags (such as `thinkingLevelMap` or custom headers).
*   🚀 **Quick Terminal**: Start a fresh terminal session of Pi directly from the interface.

---

### 🚀 Quick Start

#### 1. Install Dependencies
This project requires Python 3.9+ and `pywebview`.
```bash
pip install pywebview
```

#### 2. Launch the Application
*   **Method A**: Double-click `PiModelManager.bat` (or use the desktop shortcut).
*   **Method B**: Run via Command Prompt/PowerShell:
    ```bash
    pythonw.exe desktop_app.py
    ```

---

### 🔄 Live Sync Extension Setup

Follow these steps to enable auto-refresh on save inside running Pi terminal sessions:

1.  Copy `models-sync.ts` from this repository to your Pi global extensions directory:
    *   **Windows Path**: `%USERPROFILE%\.pi\agent\extensions\models-sync.ts`
2.  In your active Pi terminal, run `/reload` once to register the new watcher extension.
3.  Any edits made and saved in the GUI (or via `Ctrl+S`) will now apply instantly, prompting:
    > `[info] 已同步 models.json (5 providers / 16 models)`
4.  You can also force a sync manually by running `/sync-models` in the Pi session.

---

### 📂 File Structure

```text
pi-model-manager/
├── desktop_app.py      # Main Desktop App (pywebview GUI)
├── models-sync.ts      # Companion hot-reload extension for Pi
├── PiModelManager.bat  # Silent shell launcher
├── README.md           # Documentation
└── .gitignore          # Git ignore file
```

---

## 🤝 Community & Support / 社区与支持

- **LINUX DO 社区**: [https://linux.do](https://linux.do/) - 可以在此讨论和反馈此工具的使用体验及建议。
