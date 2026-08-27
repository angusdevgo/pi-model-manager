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

在 `Pi-Coding-Agent` 中引入自定义大模型服务商（如本地私有部署的 **Ollama**、**LM Studio**，或者云端的 **DeepSeek**、**OpenRouter**）以往只能通过手动编辑 JSON 配置文件 (`models.json`)。这带来了以下痛点：
1.  **极易写错格式**：少写一个逗号或引号都会导致解析失败，令 Agent 报错无法运行。
2.  **流程繁琐**：每次增删模型、修改 API 密钥或修改 URL，都需要查阅文档字段并手动打字编辑，且修改后需要重启 Pi 会话。
3.  **缓存冲突与覆盖**：内置的提供商目录或本地远程目录缓存经常会覆盖自定义的设置，使得已删除的模型在列表中复活。

**Pi 模型管理器** 提供了一个纯本地的图形化窗口，安全地读写 `models.json`。它支持自动识别 Agent 配置路径、一键拉取服务商模型、智能合并高级参数（如 `compat` 兼容标志、输入输出计费 `cost`、上下文窗口大小 `contextWindow` 等），并自带扩展，实现保存即生效的免重启同步。

---

### ✨ 功能特性

*   🖥️ **本地桌面客户端**：纯本地运行，采用现代磨砂玻璃/无边框设计风格，体验丝滑（无需开启本地网页服务器或打开浏览器）。
*   📦 **服务商管理 (CRUD)**：支持对自定义模型服务商进行可视化新增、编辑、删除。
*   🤖 **模型管理**：
    *   **自动拉取**：一键请求 API 的 `/v1/models` 点，自动获取并填充支持的模型列表。
    *   **手动管理**：支持手动键入模型 ID 和显示名称，灵活新增或删除单个模型。
*   🔄 **热更新与同步**：搭配配套 of Pi 扩展，在保存配置后自动热更新当前正在运行的 Pi 终端模型列表，**无需重启，也无需执行 `/reload`**。
*   🔒 **字段保护与合并**：保存时会自动清理无效的空字段，并智能合并现有 `models.json` 中的高级配置（如 `compat`、`cost`、`contextWindow` 等），避免丢失手动调优的参数。
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

为了在修改配置后让正在运行 of Pi 会话立刻生效，本项目附带了一个 Pi 扩展 `models-sync.ts`。

#### 安装步骤：
1.  将本项目中的 `models-sync.ts` 复制到你的 Pi 全局扩展目录中（默认路径通常为 `~/.pi/agent/extensions/models-sync.ts`）。
2.  在已打开的 Pi 终端中执行一次 `/reload` 以加载此扩展（之后就不再需要手动 reload 了）。
3.  扩展加载后，它会后台监听 `models.json` 的修改。每当你在桌面管理器中点击 **💾 保存**，Pi 终端会立刻同步，并弹出通知：
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

Adding custom model providers (e.g., local **Ollama**, **LM Studio**, or remote **DeepSeek**, **OpenRouter**) to `Pi-Coding-Agent` used to require manually editing the JSON configuration file (`models.json`). This workflow was prone to errors:
1. **Syntax Sensitivity**: A single missing comma or quote could break the agent startup.
2. **Tedious Process**: Users had to look up configuration options, edit JSON manually, and restart the CLI session or run `/reload` to sync.
3. **Registry Conflicts**: Cached remote directories and built-in overrides often merged unexpectedly, keeping deleted models active.

**Pi Model Manager** is a lightweight, local graphical desktop tool designed to manage custom providers and models safely. It features automatic config path discovery, remote model fetching, smart merging of advanced configs (`compat`, `cost`, `contextWindow`), and a companion hot-reload extension.

---

### ✨ Features

*   🖥️ **Native Desktop GUI**: Built using `pywebview`, providing a modern frosted-glass dark theme interface without starting local servers.
*   📦 **Visual CRUD**: Easily add, modify, or delete custom providers in a clean list view.
*   🤖 **Bilingual Catalog Control**:
    *   **Auto Fetch**: Requests the `/v1/models` endpoint of standard OpenAI-compatible APIs to retrieve models with one click.
    *   **Manual Entry**: Type model IDs and custom display names directly.
*   🔄 **Zero-Restart Sync (Live Sync)**: Automatically hot-updates models in your active Pi session on save using a background file watcher.
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
3.  Any edits made and saved in the GUI will now apply instantly, prompting:
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
