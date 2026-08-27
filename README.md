# Pi 模型与服务商配置管理器 (Pi Model Manager)

[English](#english) | [中文](#chinese)

---

<a id="english"></a>

## English

A modern, local graphical desktop tool for managing [Pi-Coding-Agent](https://github.com/earendil-works/pi-coding-agent) custom model providers and models, built with Python and `pywebview`.

### ⚡ Introduction

Currently, adding a custom model provider (such as Ollama, LM Studio, DeepSeek, or OpenRouter) to Pi-Coding-Agent requires manually editing the JSON configuration file (`models.json`) or asking the AI assistant to modify it. This leads to several pain points:
1. **Prone to Syntax Errors**: A missing comma or mismatched quotes can corrupt the config and prevent the agent from launching.
2. **Tedious Workflow**: Users must look up config options, manually type JSON, and restart the agent or type `/reload` in running sessions every time a configuration changes.
3. **Cache Overwrite Issues**: Built-in providers or cached catalogs can overlay on top of custom settings, making deletions or modifications hard to stick.

**Pi Model Manager** solves these issues by providing a native, beautiful desktop GUI that reads and writes `models.json` safely. It features auto-detection of agent configs, automatic remote model fetching, smart config merging (preserving custom credentials, context windows, and cost settings), and a live watcher extension that syncs configuration changes to running Pi sessions instantly without restarting.

### ✨ Features

- 🖥️ **Native Desktop Window**: Runs entirely locally as a sleek desktop app with a modern frosted glass UI (no browser or local web server required).
- 📦 **Provider Management (CRUD)**: Create, view, update, and delete custom model providers visually.
- 🤖 **Model Catalog Management**:
  - **Auto Fetch**: Fetch available models from any OpenAI-compatible `/v1/models` endpoint with a single click.
  - **Manual Input**: Add or remove custom models manually by typing IDs and display names.
- 🔄 **Live Synchronization (Hot Reload)**: Paired with the companion Pi extension, saved changes are instantly updated in your active Pi terminal **without restarting or running `/reload`**.
- 🔒 **Safe Save & Merge**: Cleans up invalid empty fields and automatically merges updates with advanced fields (such as `compat`, `cost`, `contextWindow`, etc.) present in your existing `models.json` file.
- 🚀 **Quick Launcher**: Start a new Pi terminal session directly from the desktop interface.

---

### 🚀 Quick Start

#### 1. Install Dependencies
This project requires Python 3.9+. Install the GUI wrapper dependency:
```bash
pip install pywebview
```

#### 2. Run the App
- Double-click `PiModelManager.bat` (or use the desktop shortcut `PiModelManager.lnk`).
- Alternatively, launch it via command line:
  ```bash
  pythonw.exe desktop_app.py
  ```

---

### 🔄 Setup Live Synchronization (Hot Reload)

To make running Pi sessions instantly sync configurations upon saving:

1. Copy the companion file `models-sync.ts` into your global Pi extension directory (typically `~/.pi/agent/extensions/models-sync.ts`).
2. Run `/reload` once in your active Pi terminal session to load the extension.
3. Once loaded, the extension watches `models.json` in the background. Whenever you click **💾 Save** in the desktop app, the Pi terminal automatically refreshes models and displays:
   > `[info] 已同步 models.json (5 providers / 16 models)`
4. You can also manually reload by entering `/sync-models` in the Pi terminal.

---

### 📂 File Structure

- `desktop_app.py`: Desktop application main program (Pywebview + HTML5/CSS3/JS UI).
- `models-sync.ts`: Pi agent companion sync extension.
- `PiModelManager.bat`: Invisible command prompt launcher script.
- `README.md`: Bilingual documentation.

---

<a id="chinese"></a>

## 中文

为 [Pi-Coding-Agent](https://github.com/earendil-works/pi-coding-agent) 量身定制的本地图形化桌面模型管理器，采用 Python + `pywebview` 驱动。

### ⚡ 工具介绍

目前，要在 Pi-Coding-Agent 中使用自定义的模型服务商（例如本地 Ollama、LM Studio，或云端的 DeepSeek、OpenRouter 等），用户需要手动修改 JSON 配置文件 (`models.json`)。这带来了以下痛点：
1. **容易发生格式错误**：少写一个逗号或引号都会导致 JSON 解析失败，进而导致 Agent 报错无法启动。
2. **操作繁琐**：每次增删模型、修改 API 密钥或修改 URL，都需要手动查阅文档字段并编辑，且修改后需要重启 Pi 或输入 `/reload` 命令。
3. **缓存冲突**：内置的服务商目录或本地远程目录缓存经常会覆盖自定义的设置，使得删除的模型重新出现。

**Pi 模型管理器** 提供了一个纯本地的图形化窗口，安全地读写 `models.json`。它支持自动识别 Agent 配置路径、一键拉取服务商模型、智能合并高级参数（如 `compat` 兼容标志、输入输出计费 `cost`、上下文窗口大小 `contextWindow` 等），并自带扩展，实现保存即生效的免重启同步。

### ✨ 功能特性

- 🖥️ **本地桌面客户端**：纯本地运行，采用现代磨砂玻璃/无边框设计风格，体验丝滑（无需开启本地网页服务器或打开浏览器）。
- 📦 **服务商管理 (CRUD)**：支持对自定义模型服务商进行可视化新增、编辑、删除。
- 🤖 **模型管理**：
  - **自动拉取**：一键请求 API 的 `/v1/models` 端点，自动获取并填充支持的模型列表。
  - **手动管理**：支持手动键入模型 ID 和显示名称，灵活新增或删除单个模型。
- 🔄 **热更新与同步**：搭配配套的 Pi 扩展，在保存配置后自动热更新当前正在运行的 Pi 终端模型列表，**无需重启，也无需执行 `/reload`**。
- 🔒 **字段保护与合并**：保存时会自动清理无效的空字段，并智能合并现有 `models.json` 中的高级配置（如 `compat`、`cost`、`contextWindow` 等），避免丢失手动调优的参数。
- 🚀 **一键启动**：支持在管理器中一键启动一个新的 Pi 交互式会话终端。

---

### 🚀 快速开始

#### 1. 安装依赖
本项目需要 Python 3.9+ 环境。在运行前请先安装 `pywebview`：
```bash
pip install pywebview
```

#### 2. 下载并运行
- 双击目录下的 `PiModelManager.bat` 启动管理器（或者双击桌面的 `PiModelManager` 快捷方式）。
- 也可以直接通过命令行启动：
   ```bash
   pythonw.exe desktop_app.py
   ```

---

### 🔄 实现免重启热同步 (Live Sync)

为了在修改配置后让正在运行的 Pi 会话立刻生效，本项目附带了一个 Pi 扩展 `models-sync.ts`。

#### 安装步骤：
1. 将 `models-sync.ts` 复制到你的 Pi 全局扩展目录中（默认路径通常为 `~/.pi/agent/extensions/models-sync.ts`）。
2. 在已打开的 Pi 终端中执行一次 `/reload` 以加载此扩展（之后就不再需要手动 reload 了）。
3. 扩展加载后，它会后台监听 `models.json` 的修改。每当你在桌面管理器中点击 **💾 保存**，Pi 终端会立刻同步，并弹出通知：
   > `[info] 已同步 models.json（5 个服务商 / 16 个可用模型）`
4. 你也可以在 Pi 终端中输入 `/sync-models` 手动触发同步。

---

### 📂 文件目录说明

- `desktop_app.py`：桌面客户端主程序（Pywebview + HTML5/CSS3/JS）。
- `models-sync.ts`：Pi 终端的配套同步扩展脚本（放置在 `~/.pi/agent/extensions/` 下）。
- `PiModelManager.bat`：用于后台启动应用的 Windows 批处理脚本（隐藏控制台窗口）。
- `README.md`：中英双语说明文档。
