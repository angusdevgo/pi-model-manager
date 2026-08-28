import json
import os
import subprocess
import threading
import urllib.request
import webview
from pathlib import Path

DEFAULT_AGENT_DIR = Path(os.environ.get("PI_CODING_AGENT_DIR", Path.home() / ".pi" / "agent"))
DEFAULT_MODELS_PATH = DEFAULT_AGENT_DIR / "models.json"
CONFIG_FILE_NAMES = {
    "models.json",
    "models_cache.json",
    "providers.json",
    "config.json",
    "config.toml",
    "settings.json",
    "model-providers.json",
    "model_providers.json",
    "model_config.json",
    "model-config.json",
}
CONFIG_EXTENSIONS = {".json", ".jsonc", ".toml", ".yaml", ".yml"}
AGENT_NAME_HINTS = (
    "agent",
    "agents",
    "pi",
    "codex",
    "continue",
    "cursor",
    "cline",
    "roo",
    "aider",
    "openai",
    "anthropic",
    "model",
    "provider",
)
SKIP_SCAN_DIRS = {
    "node_modules",
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    ".cache",
    "cache",
    "caches",
    "temp",
    "tmp",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "target",
    "logs",
    "screenshots",
    "screenclip",
    "packages",
    "microsoftwindows.client.core_cw5n1h2txyewy",
}
COMMON_AGENT_DIRS = [
    DEFAULT_AGENT_DIR,
    Path.home() / ".pi" / "agent",
    Path.home() / ".codex",
    Path.home() / ".config",
    Path.home() / ".continue",
    Path.home() / ".cursor",
    Path.home() / ".cline",
    Path.home() / ".roo",
    Path(os.environ.get("APPDATA", "")) if os.environ.get("APPDATA") else None,
    Path(os.environ.get("LOCALAPPDATA", "")) if os.environ.get("LOCALAPPDATA") else None,
]
CURRENT_CONFIG_PATH = DEFAULT_MODELS_PATH

def strip_json_comments(text: str) -> str:
    result = []
    in_string = False
    escaped = False
    i = 0
    while i < len(text):
        ch = text[i]
        next_ch = text[i + 1] if i + 1 < len(text) else ''
        if in_string:
            result.append(ch)
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            result.append(ch)
            i += 1
            continue
        if ch == '/' and next_ch == '/':
            while i < len(text) and text[i] != '\n':
                i += 1
            continue
        if ch == '/' and next_ch == '*':
            i += 2
            while i + 1 < len(text) and not (text[i] == '*' and text[i + 1] == '/'):
                i += 1
            i += 2
            continue
        result.append(ch)
        i += 1
    return "".join(result)

def normalize_config_path(path_value=None):
    if not path_value:
        return CURRENT_CONFIG_PATH
    return Path(str(path_value)).expanduser()

def detect_config_schema(path, data):
    if path.suffix.lower() == ".toml":
        text = data if isinstance(data, str) else ""
        if "model" in text.lower() or "mcp_servers" in text.lower():
            return "codex-toml"
        return None
    if not isinstance(data, dict):
        return None
    providers = data.get("providers")
    if isinstance(providers, dict):
        if not providers:
            return "pi-providers"
        for provider in providers.values():
            if isinstance(provider, dict) and any(key in provider for key in ("baseUrl", "apiKey", "api", "models", "headers")):
                return "pi-providers"
        for provider in providers.values():
            if isinstance(provider, dict) and "settings" in provider:
                return "cline-providers"
        return "generic-providers"
    if "models" in data and isinstance(data.get("models"), list):
        return "codex-model-cache"
    if data and all(isinstance(v, dict) and "models" in v for v in list(data.values())[:10]):
        return "opencode-model-catalog"
    if path.name.lower() == "config.json" and ("theme" in data or "$schema" in data):
        return "agent-config"
    return None

def read_config_file(path):
    raw = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".toml":
        return raw
    clean = strip_json_comments(raw).strip()
    if not clean:
        return {"providers": {}}
    return json.loads(clean)

def normalize_config_for_ui(path, data, schema):
    if schema in ("pi-providers", "generic-providers"):
        if isinstance(data, dict) and isinstance(data.get("providers"), dict):
            normalized = dict(data)
            normalized["providers"] = data.get("providers", {})
            return normalized
        return {"providers": {}}
    if schema == "cline-providers":
        providers = {}
        for pid, provider in data.get("providers", {}).items():
            settings = provider.get("settings", {}) if isinstance(provider, dict) else {}
            model = settings.get("model", "")
            providers[pid] = {
                "name": pid,
                "api": settings.get("provider", pid),
                "baseUrl": "",
                "apiKey": "",
                "models": [{"id": model, "name": model}] if model else [],
            }
        return {"providers": providers}
    if schema == "opencode-model-catalog":
        providers = {}
        for pid, provider in data.items():
            if not isinstance(provider, dict):
                continue
            raw_models = provider.get("models", {})
            models = []
            if isinstance(raw_models, dict):
                models = [{"id": mid, "name": (m.get("name") if isinstance(m, dict) else mid) or mid} for mid, m in raw_models.items()]
            elif isinstance(raw_models, list):
                for item in raw_models:
                    if isinstance(item, dict):
                        mid = item.get("id") or item.get("name")
                    else:
                        mid = str(item)
                    if mid:
                        models.append({"id": mid, "name": mid})
            providers[pid] = {"name": provider.get("name", pid), "api": provider.get("api", ""), "baseUrl": provider.get("doc", ""), "apiKey": "", "models": models}
        return {"providers": providers}
    if schema == "codex-model-cache":
        models = []
        for item in data.get("models", []):
            if isinstance(item, dict):
                mid = item.get("id") or item.get("name")
                if mid:
                    models.append({"id": mid, "name": item.get("name", mid)})
        return {"providers": {"codex": {"name": "Codex model cache", "api": "codex", "baseUrl": "", "apiKey": "", "models": models}}}
    if schema == "codex-toml":
        model = ""
        for line in data.splitlines():
            line = line.strip()
            if line.startswith("model") and "=" in line:
                model = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
        return {"providers": {"codex": {"name": "Codex config", "api": "toml", "baseUrl": "", "apiKey": "", "models": [{"id": model, "name": model}] if model else []}}}
    return {"providers": {}}

def is_editable_schema(schema):
    return schema in ("pi-providers", "generic-providers")

def load_config(path_value=None):
    path = normalize_config_path(path_value)
    if not path.exists():
        return {"providers": {}}
    try:
        data = read_config_file(path)
        schema = detect_config_schema(path, data)
        return normalize_config_for_ui(path, data, schema)
    except Exception:
        return {"providers": {}}

def clean_pi_config(cfg):
    if not isinstance(cfg, dict):
        return {"providers": {}}
    providers = cfg.get("providers")
    if not isinstance(providers, dict):
        cfg["providers"] = {}
        return cfg
    for provider in providers.values():
        if not isinstance(provider, dict):
            continue
        for key in ("name", "baseUrl", "apiKey", "api", "authHeader"):
            if provider.get(key) == "":
                provider.pop(key, None)
        models = provider.get("models")
        if isinstance(models, list):
            cleaned = []
            seen = set()
            for model in models:
                if not isinstance(model, dict):
                    continue
                model_id = str(model.get("id", "")).strip()
                if not model_id or model_id in seen:
                    continue
                seen.add(model_id)
                model["id"] = model_id
                for key in ("name", "api", "baseUrl"):
                    if model.get(key) == "":
                        model.pop(key, None)
                cleaned.append(model)
            provider["models"] = cleaned
    return cfg

def merge_model_lists(old_models, new_models):
    old_by_id = {}
    if isinstance(old_models, list):
        for model in old_models:
            if isinstance(model, dict) and model.get("id"):
                old_by_id[str(model["id"])] = dict(model)
    merged = []
    seen = set()
    if isinstance(new_models, list):
        for model in new_models:
            if not isinstance(model, dict):
                continue
            model_id = str(model.get("id", "")).strip()
            if not model_id or model_id in seen:
                continue
            seen.add(model_id)
            item = dict(old_by_id.get(model_id, {}))
            item.update(model)
            merged.append(item)
    return merged

def merge_pi_config(existing, incoming):
    existing = existing if isinstance(existing, dict) else {}
    incoming = incoming if isinstance(incoming, dict) else {"providers": {}}
    existing_providers = existing.get("providers") if isinstance(existing.get("providers"), dict) else {}
    incoming_providers = incoming.get("providers") if isinstance(incoming.get("providers"), dict) else {}
    merged = dict(existing)
    merged["providers"] = {}
    for pid, provider in incoming_providers.items():
        old = existing_providers.get(pid) if isinstance(existing_providers.get(pid), dict) else {}
        new_provider = dict(old)
        if isinstance(provider, dict):
            new_provider.update(provider)
            if "models" in provider:
                new_provider["models"] = merge_model_lists(old.get("models"), provider.get("models"))
        merged["providers"][pid] = new_provider
    return clean_pi_config(merged)

def save_config(cfg, path_value=None):
    path = normalize_config_path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if path.exists():
        try:
            existing = read_config_file(path)
        except Exception:
            existing = {}
    cfg = merge_pi_config(existing, cfg)
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def display_name_for_config(path, ui_config, schema, editable):
    try:
        rel = path.relative_to(Path.home())
        short_path = f"~\\{rel}"
    except ValueError:
        short_path = str(path)
    lower = str(path).lower()
    if "\\.pi\\agent" in lower or "/.pi/agent" in lower:
        prefix = "Pi Agent"
    elif "opencode" in lower:
        prefix = "opencode"
    elif "codex" in lower:
        prefix = "Codex"
    elif "cline" in lower:
        prefix = "Cline"
    elif "agy" in lower:
        prefix = "Agy"
    elif "continue" in lower:
        prefix = "Continue"
    elif "cursor" in lower:
        prefix = "Cursor"
    elif "roo" in lower:
        prefix = "Roo"
    else:
        prefix = "Agent"
    count = len(ui_config.get("providers", {})) if isinstance(ui_config, dict) else 0
    mode = "可编辑" if editable else "只读预览"
    return f"{prefix} · {path.name} · {count} providers · {mode} · {short_path}"

def candidate_has_agent_hint(path):
    lower_parts = [part.lower() for part in path.parts]
    file_name = path.name.lower()
    if file_name in CONFIG_FILE_NAMES:
        return True
    if any(hint in file_name for hint in ("model", "provider", "agent")):
        return any(any(hint in part for hint in AGENT_NAME_HINTS) for part in lower_parts)
    return False

def should_skip_dir(path):
    name = path.name.lower()
    lower = str(path).lower()
    if "node_modules" in lower or "\\.cache\\codex-runtimes" in lower or "/.cache/codex-runtimes" in lower:
        return True
    if "opencode" in lower or "codex" in lower or "cline" in lower or "agy" in lower:
        return name in {"node_modules", ".git", "dist", "build", "tmp", "temp"}
    if name in SKIP_SCAN_DIRS:
        return True
    if name.endswith("cache") or name.endswith("temp"):
        return True
    return False

def path_has_agent_hint(path):
    lower = str(path).lower()
    return any(hint in lower for hint in AGENT_NAME_HINTS)

def should_descend_dir(path, depth):
    if should_skip_dir(path):
        return False
    name = path.name.lower()
    if depth == 0:
        return name.startswith(".") or name in {"appdata"} or path_has_agent_hint(path)
    return path_has_agent_hint(path) or any(part.lower() in {".config", ".pi", "appdata", "roaming", "local"} for part in path.parts)

def iter_user_config_candidates(root, max_depth=7, max_files=1600, max_dirs=900):
    root = Path(root)
    queue = [(root, 0)]
    seen_files = 0
    seen_dirs = 0
    while queue and seen_files < max_files and seen_dirs < max_dirs:
        directory, depth = queue.pop(0)
        seen_dirs += 1
        if depth > max_depth or should_skip_dir(directory):
            continue
        try:
            entries = list(directory.iterdir())
        except Exception:
            continue
        for entry in entries:
            try:
                if entry.is_dir():
                    if should_descend_dir(entry, depth):
                        queue.append((entry, depth + 1))
                elif entry.is_file() and entry.suffix.lower() in CONFIG_EXTENSIONS:
                    seen_files += 1
                    if candidate_has_agent_hint(entry):
                        yield entry
            except Exception:
                continue

def discover_config_targets():
    path = DEFAULT_MODELS_PATH.resolve()
    config = load_config(path)
    return [{
        "label": display_name_for_config(path, config, "pi-providers", True),
        "path": str(path),
        "providerCount": len(config.get("providers", {})),
        "exists": path.exists(),
        "schema": "pi-providers",
        "editable": True,
    }]

def fetch_models(base_url, api_key):
    url = base_url.rstrip("/")
    if url.endswith("/v1"):
        endpoint = f"{url}/models"
    elif url.endswith("/models"):
        endpoint = url
    else:
        endpoint = f"{url}/v1/models"
    
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    req = urllib.request.Request(endpoint, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    
    items = []
    if "data" in body and isinstance(body["data"], list):
        items = body["data"]
    elif "models" in body and isinstance(body["models"], list):
        items = body["models"]
    elif isinstance(body, list):
        items = body
    
    models = []
    for it in items:
        mid = it.get("id") or it.get("name")
        if mid:
            name = it.get("name") or mid
            models.append({"id": str(mid), "name": str(name)})
    return sorted(models, key=lambda x: x["id"])

class ApiBridge:
    def __init__(self):
        self._window = None

    def set_window(self, win):
        self._window = win

    def discover_configs(self):
        return {"targets": discover_config_targets(), "defaultPath": str(DEFAULT_MODELS_PATH)}

    def get_config(self, path=None):
        config_path = normalize_config_path(path)
        schema = "pi-providers"
        editable = True
        if config_path.exists():
            try:
                raw_data = read_config_file(config_path)
                schema = detect_config_schema(config_path, raw_data) or "unknown"
                editable = is_editable_schema(schema)
            except Exception:
                schema = "unknown"
                editable = False
        return {"config": load_config(config_path), "path": str(config_path), "schema": schema, "editable": editable}

    def save_config(self, config_json_str, path=None):
        try:
            config_path = normalize_config_path(path)
            if config_path.exists():
                raw_data = read_config_file(config_path)
                schema = detect_config_schema(config_path, raw_data)
                if not is_editable_schema(schema):
                    return {"success": False, "error": "当前配置格式为只读预览，不能直接写回。"}
            data = json.loads(config_json_str) if isinstance(config_json_str, str) else config_json_str
            save_config(data, config_path)
            saved = load_config(config_path)
            model_count = sum(len(provider.get("models", [])) for provider in saved.get("providers", {}).values() if isinstance(provider, dict))
            return {"success": True, "providerCount": len(saved.get("providers", {})), "modelCount": model_count}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def fetch_models(self, base_url, api_key):
        try:
            models = fetch_models(base_url, api_key)
            return {"success": True, "models": models}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def restart_pi(self):
        try:
            subprocess.Popen(["wt.exe", "powershell.exe", "-NoExit", "-Command", "pi"], shell=True)
        except Exception:
            subprocess.Popen(["cmd.exe", "/c", "start", "powershell.exe", "-NoExit", "-Command", "pi"], shell=True)
        return {"success": True}

    def minimize_window(self):
        if self._window:
            self._window.minimize()

    def maximize_window(self):
        if self._window:
            if hasattr(self._window, 'toggle_fullscreen'):
                # Check maximized state or toggle
                pass
            # pywebview maximize / restore
            try:
                self._window.restore() if getattr(self, '_maximized', False) else self._window.maximize()
                self._maximized = not getattr(self, '_maximized', False)
            except Exception:
                pass

    def close_window(self):
        if self._window:
            self._window.destroy()

HTML_CONTENT = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pi模型配置</title>
<style>
  :root {
    --bg-gradient: radial-gradient(circle at 10% 10%, rgba(30, 41, 59, 0.96) 0%, rgba(15, 23, 42, 0.99) 100%);
    --card-bg: rgba(30, 41, 59, 0.45);
    --card-hover: rgba(51, 65, 85, 0.55);
    --glass-border: rgba(255, 255, 255, 0.08);
    --glass-border-focus: rgba(96, 165, 250, 0.4);
    --input-bg: rgba(11, 17, 32, 0.55);
    --primary: #3B82F6;
    --primary-hover: #2563EB;
    --emerald: #10B981;
    --emerald-hover: #059669;
    --rose: #EF4444;
    --rose-hover: #DC2626;
    --text-main: #F8FAFC;
    --text-muted: #94A3B8;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif; user-select: none; }
  
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.12); border-radius: 4px; }
  ::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.22); }

  body {
    background: var(--bg-gradient);
    color: var(--text-main);
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border: 1px solid var(--glass-border);
    border-radius: 10px;
  }
  
  /* 自定义现代化无边框标题栏与导航合一 */
  header {
    background: rgba(30, 41, 59, 0.65);
    backdrop-filter: blur(20px);
    border-bottom: 1px solid var(--glass-border);
    padding: 0 16px 0 20px;
    height: 54px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;
    min-width: 0;
    flex: 1;
  }

  .logo-title {
    font-size: 16px;
    font-weight: 700;
    color: #60A5FA;
    display: flex;
    align-items: center;
    gap: 8px;
    white-space: nowrap;
    flex-shrink: 0;
    text-shadow: 0 0 14px rgba(96, 165, 250, 0.35);
  }
  
  .path-badge, .target-select {
    font-size: 12px;
    color: var(--text-muted);
    background: rgba(15, 23, 42, 0.65);
    padding: 5px 12px;
    border-radius: 6px;
    border: 1px solid var(--glass-border);
  }
  .target-select {
    color: var(--text-main);
    width: min(360px, 32vw);
    min-width: 160px;
    outline: none;
  }
  .target-select:focus { border-color: var(--glass-border-focus); }

  .header-right {
    display: flex;
    align-items: center;
    gap: 14px;
    flex-shrink: 0;
  }

  .header-actions {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
  }

  /* 窗口控制三键 (最小化、最大化、关闭) */
  .window-controls {
    display: flex;
    align-items: center;
    margin-left: 6px;
    border-left: 1px solid var(--glass-border);
    padding-left: 10px;
  }
  .win-btn {
    width: 32px;
    height: 32px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    color: var(--text-muted);
    font-size: 13px;
    transition: all 0.15s ease;
  }
  .win-btn:hover {
    background: rgba(255, 255, 255, 0.1);
    color: var(--text-main);
  }
  .win-btn.close:hover {
    background: #EF4444;
    color: white;
  }

  .btn { border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 7px; padding: 6px 16px; font-size: 13px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; gap: 6px; white-space: nowrap; transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); box-shadow: 0 2px 6px rgba(0,0,0,0.2); }
  .btn-primary { background: linear-gradient(135deg, #3B82F6, #2563EB); color: white; }
  .btn-primary:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(59, 130, 246, 0.35); border-color: rgba(255, 255, 255, 0.25); }
  .btn-emerald { background: linear-gradient(135deg, #10B981, #059669); color: white; }
  .btn-emerald:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(16, 185, 129, 0.35); border-color: rgba(255, 255, 255, 0.25); }
  .btn-rose { background: linear-gradient(135deg, #EF4444, #DC2626); color: white; }
  .btn-rose:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(239, 68, 68, 0.35); }
  .btn-secondary { background: rgba(71, 85, 105, 0.6); color: white; border: 1px solid var(--glass-border); }
  .btn-secondary:hover { background: rgba(100, 116, 139, 0.8); }

  .layout { display: flex; flex: 1; overflow: hidden; }
  .sidebar { width: 320px; background: rgba(30, 41, 59, 0.35); backdrop-filter: blur(16px); border-right: 1px solid var(--glass-border); display: flex; flex-direction: column; }
  .sidebar-header { padding: 14px 16px; border-bottom: 1px solid var(--glass-border); display: flex; justify-content: space-between; align-items: center; font-size: 14px; font-weight: 600; }
  .provider-list { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 8px; }
  
  .p-card { background: rgba(15, 23, 42, 0.45); backdrop-filter: blur(12px); border: 1px solid var(--glass-border); border-radius: 9px; padding: 11px 13px; cursor: pointer; transition: all 0.2s ease; box-shadow: 0 2px 6px rgba(0,0,0,0.15); }
  .p-card:hover { border-color: var(--glass-border-focus); background: rgba(30, 58, 138, 0.25); transform: translateY(-1px); }
  .p-card.active { border-color: #60A5FA; background: rgba(30, 58, 138, 0.4); box-shadow: 0 0 14px rgba(96, 165, 250, 0.2); }
  .p-card-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 3px; }
  .p-name { font-weight: 600; font-size: 14px; color: var(--text-main); }
  .p-id { font-size: 12px; color: var(--text-muted); }
  .p-count { font-size: 11px; background: rgba(51, 65, 85, 0.7); padding: 2px 8px; border-radius: 6px; color: #93C5FD; border: 1px solid var(--glass-border); }

  .main-content { flex: 1; overflow-y: auto; padding: 20px 24px; display: flex; flex-direction: column; gap: 16px; }
  .card { background: var(--card-bg); backdrop-filter: blur(16px); border: 1px solid var(--glass-border); border-radius: 12px; padding: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.25); }
  .card-title { font-size: 14px; font-weight: 700; margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; }
  
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .form-group { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
  .form-group label { font-size: 12px; font-weight: 600; color: var(--text-muted); }
  .input { background: var(--input-bg); border: 1px solid var(--glass-border); border-radius: 7px; padding: 9px 12px; color: var(--text-main); font-size: 13px; outline: none; user-select: text; transition: border-color 0.2s, box-shadow 0.2s; }
  .input:focus { border-color: #60A5FA; box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.2); }
  select.input { cursor: pointer; }

  .models-tag-container { display: flex; flex-direction: column; gap: 8px; max-height: 240px; overflow-y: auto; padding: 12px; background: rgba(11, 17, 32, 0.45); border-radius: 9px; border: 1px solid var(--glass-border); }
  .model-tag { display: flex; align-items: center; gap: 8px; background: linear-gradient(135deg, rgba(51, 65, 85, 0.6), rgba(30, 41, 59, 0.75)); border: 1px solid var(--glass-border); border-radius: 8px; padding: 5px 12px; font-size: 12px; backdrop-filter: blur(6px); transition: all 0.2s ease; }
  .model-tag:hover { border-color: rgba(96, 165, 250, 0.4); background: linear-gradient(135deg, rgba(51, 65, 85, 0.8), rgba(37, 51, 79, 0.85)); transform: translateX(3px); box-shadow: 0 2px 10px rgba(0,0,0,0.2); }
  .model-tag .alias-icon { font-size: 11px; flex-shrink: 0; opacity: 0.75; }
  .model-tag .alias-input { background: transparent; border: 1px dashed transparent; border-radius: 5px; color: var(--emerald); font-size: 12.5px; font-weight: 600; width: 170px; padding: 2px 6px; outline: none; font-family: inherit; transition: all 0.15s; }
  .model-tag .alias-input:hover { border-color: var(--glass-border); background: rgba(11, 17, 32, 0.4); }
  .model-tag .alias-input:focus { border-color: #60A5FA; background: rgba(11, 17, 32, 0.65); box-shadow: 0 0 0 2px rgba(96, 165, 250, 0.18); }
  .model-tag .alias-id { font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 11px; color: #94A3B8; flex-shrink: 0; background: rgba(11, 17, 32, 0.35); padding: 1px 6px; border-radius: 4px; }
  .model-tag .del-btn { cursor: pointer; color: var(--text-muted); font-size: 14px; padding: 0 3px; border-radius: 4px; flex-shrink: 0; transition: all 0.15s; }
  .model-tag .del-btn:hover { color: #fff; background: rgba(244, 63, 94, 0.35); }

  .fetch-preview-container { display: none; margin-top: 14px; padding: 14px; background: linear-gradient(135deg, rgba(15, 23, 42, 0.8), rgba(30, 41, 59, 0.65)); border-radius: 11px; border: 1px solid rgba(96, 165, 250, 0.4); box-shadow: 0 0 20px rgba(96, 165, 250, 0.1); }
  .fetch-preview-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; gap: 10px; flex-wrap: wrap; }
  .fetch-preview-header .title { background: linear-gradient(90deg, #60A5FA, #818CF8); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; font-size: 13.5px; font-weight: 700; }
  .fetch-preview-header .actions { display: flex; gap: 8px; flex-wrap: wrap; }
  .fetch-preview-header .actions .btn { padding: 4px 11px; font-size: 12px; border-radius: 6px; }
  .fetch-preview-list { display: flex; flex-direction: column; gap: 6px; max-height: 240px; overflow-y: auto; }
  .fetch-row { display: flex; align-items: center; gap: 10px; padding: 6px 11px; background: rgba(30, 41, 59, 0.5); border: 1px solid var(--glass-border); border-radius: 8px; transition: all 0.15s; }
  .fetch-row:hover { background: rgba(51, 65, 85, 0.65); border-color: rgba(96, 165, 250, 0.35); }
  .fetch-row.added { opacity: 0.45; }
  .fetch-row .checkbox { width: 16px; height: 16px; cursor: pointer; flex-shrink: 0; accent-color: var(--primary); }
  .fetch-row .model-id { font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 12px; color: var(--emerald); min-width: 170px; flex-shrink: 0; }
  .fetch-row .alias-input { flex: 1; background: rgba(11, 17, 32, 0.6); border: 1px solid var(--glass-border); border-radius: 6px; color: #fff; font-size: 12px; padding: 4px 9px; outline: none; font-family: inherit; transition: border-color 0.15s; }
  .fetch-row .alias-input:focus { border-color: #60A5FA; box-shadow: 0 0 0 2px rgba(96, 165, 250, 0.15); }
  .fetch-row .alias-input::placeholder { color: var(--text-muted); }
  .fetch-row .status-badge { font-size: 11px; padding: 2px 8px; border-radius: 5px; background: rgba(16, 185, 129, 0.15); color: var(--emerald); flex-shrink: 0; border: 1px solid rgba(16, 185, 129, 0.3); }
  .fetch-summary { font-size: 12px; color: var(--text-muted); margin-bottom: 9px; padding: 6px 10px; background: rgba(11, 17, 32, 0.35); border-radius: 6px; }

  footer { background: rgba(30, 41, 59, 0.5); backdrop-filter: blur(16px); border-top: 1px solid var(--glass-border); padding: 7px 20px; font-size: 12px; color: var(--emerald); display: flex; justify-content: space-between; }
</style>
</head>
<body>

<header class="pywebview-drag-region">
  <div class="header-left">
    <div class="logo-title">⚡ Pi模型配置</div>
    <select class="target-select" id="targetSelect" title="Pi Agent 配置文件" onchange="switchTarget()"></select>
  </div>

  <div class="header-right">
    <div class="header-actions">
      <button class="btn btn-primary" id="saveBtn" onclick="saveAll()" title="保存到 models.json。已打开的 Pi 会自动同步；若尚未加载 models-sync 扩展，请先执行一次 /reload">💾 保存</button>
      <button class="btn btn-emerald" onclick="restartPi()" title="保存配置并打开一个新的 Pi 会话">🔄 重启</button>
    </div>
    
    <div class="window-controls">
      <div class="win-btn" title="最小化" onclick="window.pywebview.api.minimize_window()">—</div>
      <div class="win-btn" title="最大化/还原" onclick="window.pywebview.api.maximize_window()">▢</div>
      <div class="win-btn close" title="关闭" onclick="window.pywebview.api.close_window()">✕</div>
    </div>
  </div>
</header>

<div class="layout">
  <div class="sidebar">
    <div class="sidebar-header">
      <span>已配置服务商</span>
      <button class="btn btn-secondary edit-action" style="padding: 3px 8px; font-size: 12px;" onclick="newProvider()">➕ 新建</button>
    </div>
    <div class="provider-list" id="providerList"></div>
  </div>

  <div class="main-content">
    <div class="card">
      <div class="card-title">
        <span>🛠️ 服务商详情 (Provider)</span>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-emerald edit-action" onclick="fetchRemoteModels()">🔄 自动拉取模型</button>
          <button class="btn btn-rose edit-action" onclick="deleteCurrentProvider()">🗑️ 删除服务商</button>
        </div>
      </div>
      <div class="grid-2">
        <div class="form-group">
          <label>服务商 ID *</label>
          <input class="input" id="pId" placeholder="例如: openrouter, deepseek, ollama">
        </div>
        <div class="form-group">
          <label>显示名称 (可选)</label>
          <input class="input" id="pName" placeholder="例如: DeepSeek Official">
        </div>
      </div>
      <div class="grid-2">
        <div class="form-group">
          <label>Base URL *</label>
          <input class="input" id="pBaseUrl" placeholder="例如: https://api.deepseek.com/v1">
        </div>
        <div class="form-group">
          <label>API Key</label>
          <input class="input" type="password" id="pApiKey" placeholder="sk-...">
        </div>
      </div>
      <div class="form-group">
        <label>API 协议类型</label>
        <select class="input" id="pApi">
          <option value="openai-completions">openai-completions (标准 OpenAI 补全)</option>
          <option value="openai-responses">openai-responses (OpenAI Responses 模式)</option>
          <option value="anthropic-messages">anthropic-messages (Anthropic 原生)</option>
          <option value="google-generative-ai">google-generative-ai (Gemini 原生)</option>
        </select>
      </div>
    </div>

    <div class="card">
      <div class="card-title">
        <span>🤖 模型管理 (Models)</span>
      </div>
      <div style="display: flex; gap: 10px; margin-bottom: 12px;">
        <input class="input" id="newModelId" placeholder="模型 ID (如: deepseek-chat)" style="flex: 1;">
        <input class="input" id="newModelName" placeholder="显示名称 / 别名 (可选)" style="flex: 1;">
        <button class="btn btn-primary edit-action" onclick="addModelManual()">➕ 添加模型</button>
      </div>
      <div class="models-tag-container" id="modelsContainer">
        <span style="color: var(--text-muted); font-size: 13px;">暂无模型，可点击上方「自动拉取模型」或手动添加。别名可直接点击修改</span>
      </div>
      <div class="fetch-preview-container" id="fetchPreviewContainer">
        <div class="fetch-preview-header">
          <span class="title">📥 拉取结果预览 — 勾选后点击「添加选中」才写入列表，可先设置别名</span>
          <div class="actions">
            <button class="btn btn-emerald edit-action" onclick="commitFetchedModels()">✅ 添加选中到列表</button>
            <button class="btn edit-action" onclick="toggleAllFetched(true)">☑ 全选</button>
            <button class="btn edit-action" onclick="toggleAllFetched(false)">☐ 全不选</button>
            <button class="btn edit-action" onclick="closeFetchPreview()">✕ 关闭</button>
          </div>
        </div>
        <div class="fetch-summary" id="fetchSummary"></div>
        <div class="fetch-preview-list" id="fetchPreviewList"></div>
      </div>
    </div>
  </div>
</div>

<footer>
  <span id="statusMsg">● 就绪</span>
  <span id="pathDisplay">保存后会自动同步到已打开的 Pi</span>
</footer>

<script>
let currentConfig = { providers: {} };
let selectedPid = null;
let configTargets = [];
let currentConfigPath = null;
let currentEditable = true;
let currentSchema = 'pi-providers';
let fetchedPreview = []; // Buffer of {id, name, selected, added}

async function refreshTargets(keepPath = true) {
  setStatus('正在加载 Pi Agent 配置文件...', '#F59E0B');
  const result = await window.pywebview.api.discover_configs();
  configTargets = result.targets || [];
  const select = document.getElementById('targetSelect');
  const previousPath = keepPath ? currentConfigPath : null;
  select.innerHTML = '';
  configTargets.forEach(target => {
    const option = document.createElement('option');
    option.value = target.path;
    option.textContent = target.label;
    select.appendChild(option);
  });
  if (previousPath && configTargets.some(t => t.path === previousPath)) {
    select.value = previousPath;
  } else if (configTargets.length > 0) {
    select.value = configTargets[0].path;
  }
  currentConfigPath = select.value || result.defaultPath;
  await loadData(currentConfigPath);
  setStatus('已加载 Pi Agent 配置文件', '#10B981');
}

async function switchTarget() {
  const select = document.getElementById('targetSelect');
  currentConfigPath = select.value;
  selectedPid = null;
  await loadData(currentConfigPath);
}

async function loadData(path = currentConfigPath) {
  const data = await window.pywebview.api.get_config(path);
  currentConfig = data.config;
  currentConfigPath = data.path;
  currentEditable = data.editable !== false;
  currentSchema = data.schema || 'unknown';
  fetchedPreview = []; // clear buffer when reloading data
  const fpContainer = document.getElementById('fetchPreviewContainer');
  if (fpContainer) fpContainer.style.display = 'none';
  document.getElementById('pathDisplay').innerText = `📁 当前配置: ${data.path}`;
  updateEditState();
  renderSidebar();
  if (selectedPid && currentConfig.providers[selectedPid]) {
    selectProvider(selectedPid);
  } else {
    const keys = Object.keys(currentConfig.providers);
    if (keys.length > 0) selectProvider(keys[0]);
    else newProvider(true);
  }
}

function updateEditState() {
  const saveBtn = document.getElementById('saveBtn');
  if (saveBtn) {
    saveBtn.disabled = !currentEditable;
    saveBtn.style.opacity = currentEditable ? '1' : '0.45';
    saveBtn.style.cursor = currentEditable ? 'pointer' : 'not-allowed';
  }
  document.querySelectorAll('.edit-action').forEach(btn => {
    btn.disabled = !currentEditable;
    btn.style.opacity = currentEditable ? '1' : '0.45';
    btn.style.cursor = currentEditable ? 'pointer' : 'not-allowed';
  });
}

function assertEditable() {
  if (currentEditable) return true;
  alert('当前配置是只读预览格式，暂不直接写回，避免破坏该 Agent 的原配置。');
  return false;
}

function renderSidebar() {
  const container = document.getElementById('providerList');
  container.innerHTML = '';
  const pids = Object.keys(currentConfig.providers).sort();
  pids.forEach(pid => {
    const p = currentConfig.providers[pid];
    const count = (p.models || []).length;
    const card = document.createElement('div');
    card.className = 'p-card' + (pid === selectedPid ? ' active' : '');
    card.onclick = () => selectProvider(pid);
    card.innerHTML = `
      <div class="p-card-top">
        <span class="p-name">${p.name || pid}</span>
        <span class="p-count">${count} models</span>
      </div>
      <div class="p-id">${pid}</div>
    `;
    container.appendChild(card);
  });
}

function selectProvider(pid) {
  selectedPid = pid;
  fetchedPreview = []; // clear buffer when switching providers
  const fpContainer = document.getElementById('fetchPreviewContainer');
  if (fpContainer) fpContainer.style.display = 'none';
  renderSidebar();
  const p = currentConfig.providers[pid] || {};
  document.getElementById('pId').value = pid;
  document.getElementById('pName').value = p.name || '';
  document.getElementById('pBaseUrl').value = p.baseUrl || '';
  document.getElementById('pApiKey').value = p.apiKey || '';
  document.getElementById('pApi').value = p.api || 'openai-completions';
  renderModels(p.models || []);
}

function renderModels(models) {
  const container = document.getElementById('modelsContainer');
  container.innerHTML = '';
  if (!models || models.length === 0) {
    container.innerHTML = '<span style="color: var(--text-muted); font-size: 13px;">暂无模型，点击「自动拉取模型」或手动添加。别名可直接点击修改</span>';
    return;
  }
  models.forEach(m => {
    const tag = document.createElement('div');
    tag.className = 'model-tag';
    const alias = m.name || m.id;
    const safeId = String(m.id).replace(/'/g, "\\'").replace(/"/g, '&quot;');
    const safeAlias = String(alias).replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    tag.innerHTML = `
      <span class="alias-icon">✏️</span>
      <input class="alias-input" type="text" value="${safeAlias}" placeholder="${safeId}"
             title="点击直接修改别名，回车或失焦自动保存"
             onchange="updateModelAlias('${safeId}', this.value)">
      <span class="alias-id">${safeId}</span>
      <span class="del-btn" onclick="removeModel('${safeId}')" title="删除该模型">✕</span>
    `;
    container.appendChild(tag);
  });
}

function updateModelAlias(mid, newAlias) {
  if (!assertEditable()) return;
  const pid = syncCurrentFormToMemory();
  if (!pid) return;
  const p = currentConfig.providers[pid];
  if (!p || !p.models) return;
  const trimmed = String(newAlias || '').trim();
  const m = p.models.find(x => x.id === mid);
  if (!m) return;
  if (!trimmed || trimmed === mid) {
    delete m.name;
  } else {
    m.name = trimmed;
  }
  renderSidebar();
}


function normalizeProviderId(raw) {
  return String(raw || '').trim().replace(/[^A-Za-z0-9_.-]+/g, '-');
}

function syncCurrentFormToMemory() {
  const pid = normalizeProviderId(document.getElementById('pId').value);
  if (!pid) return;
  if (selectedPid && selectedPid !== pid) {
    if (currentConfig.providers[pid]) {
      alert('该服务商 ID 已存在');
      document.getElementById('pId').value = selectedPid;
      return selectedPid;
    }
    currentConfig.providers[pid] = currentConfig.providers[selectedPid] || { models: [] };
    delete currentConfig.providers[selectedPid];
    selectedPid = pid;
  }
  if (!currentConfig.providers[pid]) {
    currentConfig.providers[pid] = { models: [] };
  }
  const p = currentConfig.providers[pid];
  const displayName = document.getElementById('pName').value.trim();
  const baseUrl = document.getElementById('pBaseUrl').value.trim().replace(/\\/+$/, '');
  const apiKey = document.getElementById('pApiKey').value.trim();
  const api = document.getElementById('pApi').value;

  if (displayName) p.name = displayName; else delete p.name;
  if (baseUrl) p.baseUrl = baseUrl; else delete p.baseUrl;
  if (apiKey) p.apiKey = apiKey; else delete p.apiKey;
  if (api) p.api = api; else delete p.api;
  if (!p.models) p.models = [];
  return pid;
}

function newProvider(skipEditableCheck = false) {
  if (!skipEditableCheck && !assertEditable()) return;
  selectedPid = null;
  fetchedPreview = [];
  const fpContainer = document.getElementById('fetchPreviewContainer');
  if (fpContainer) fpContainer.style.display = 'none';
  renderSidebar();
  document.getElementById('pId').value = '';
  document.getElementById('pName').value = '';
  document.getElementById('pBaseUrl').value = '';
  document.getElementById('pApiKey').value = '';
  document.getElementById('pApi').value = 'openai-completions';
  renderModels([]);
  document.getElementById('pId').focus();
}

function addModelManual() {
  if (!assertEditable()) return;
  const mid = document.getElementById('newModelId').value.trim();
  const mname = document.getElementById('newModelName').value.trim();
  if (!mid) return alert('请输入模型 ID');
  const pid = syncCurrentFormToMemory();
  if (!pid) return alert('请先输入服务商 ID');
  const p = currentConfig.providers[pid];
  const list = (p.models || []).filter(x => x.id !== mid);
  const nextModel = { id: mid };
  if (mname) nextModel.name = mname;
  list.push(nextModel);
  p.models = list.sort((a,b) => a.id.localeCompare(b.id));
  document.getElementById('newModelId').value = '';
  document.getElementById('newModelName').value = '';
  renderModels(p.models);
  renderSidebar();
  // 连续添加时自动聚焦到模型 ID 输入框
  document.getElementById('newModelId').focus();
  setStatus(`已添加模型 [${mid}]，点击「💾 保存」持久化`, '#10B981');
}

function removeModel(mid) {
  if (!assertEditable()) return;
  const pid = syncCurrentFormToMemory();
  if (!pid) return;
  const p = currentConfig.providers[pid];
  p.models = (p.models || []).filter(x => x.id !== mid);
  renderModels(p.models);
  renderSidebar();
}

async function fetchRemoteModels() {
  if (!assertEditable()) return;
  const baseUrl = document.getElementById('pBaseUrl').value.trim();
  const apiKey = document.getElementById('pApiKey').value.trim();
  if (!baseUrl) return alert('请先填写 Base URL');
  setStatus('正在拉取模型中...', '#F59E0B');
  try {
    const res = await window.pywebview.api.fetch_models(baseUrl, apiKey);
    if (!res.success) throw new Error(res.error || '拉取失败');
    const pid = syncCurrentFormToMemory();
    const existing = currentConfig.providers[pid].models || [];
    const existingIds = new Set(existing.map(m => m.id));
    // Initialize preview buffer; default-select items NOT already in the list
    fetchedPreview = res.models.map(m => ({
      id: m.id,
      name: m.name || m.id,
      selected: !existingIds.has(m.id),
      added: existingIds.has(m.id),
    }));
    renderFetchPreview();
    setStatus(`成功拉取到 ${res.models.length} 个模型，请在预览区勾选后点击「添加选中到列表」`, '#10B981');
  } catch (err) {
    alert('拉取模型失败: ' + err.message);
    setStatus('拉取模型失败: ' + err.message, '#EF4444');
  }
}

function renderFetchPreview() {
  const wrap = document.getElementById('fetchPreviewContainer');
  const list = document.getElementById('fetchPreviewList');
  const summary = document.getElementById('fetchSummary');
  if (!fetchedPreview || fetchedPreview.length === 0) {
    wrap.style.display = 'none';
    return;
  }
  wrap.style.display = 'block';
  list.innerHTML = '';
  const selectedCount = fetchedPreview.filter(m => m.selected && !m.added).length;
  const addedCount = fetchedPreview.filter(m => m.added).length;
  summary.innerHTML = `共拉取 <b style="color:#fff;">${fetchedPreview.length}</b> 个模型 · 已选 <b style="color:var(--primary);">${selectedCount}</b> 个 · 已在列表中 <b style="color:var(--emerald);">${addedCount}</b> 个`;
  fetchedPreview.forEach((m, idx) => {
    const row = document.createElement('div');
    row.className = 'fetch-row' + (m.added ? ' added' : '');
    const safeId = String(m.id).replace(/'/g, "\\'").replace(/"/g, '&quot;');
    const safeName = String(m.name).replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    row.innerHTML = `
      <input type="checkbox" class="checkbox" ${m.selected ? 'checked' : ''} ${m.added ? 'disabled' : ''}
             onchange="fetchedPreview[${idx}].selected = this.checked; updateFetchSummary();">
      <span class="model-id">${safeId}</span>
      <input type="text" class="alias-input" value="${safeName}" placeholder="为该模型设置别名（可选）"
             onchange="fetchedPreview[${idx}].name = this.value.trim() || fetchedPreview[${idx}].id">
      ${m.added ? '<span class="status-badge">已在列表中</span>' : ''}
    `;
    list.appendChild(row);
  });
}

function updateFetchSummary() {
  const summary = document.getElementById('fetchSummary');
  if (!summary || fetchedPreview.length === 0) return;
  const selectedCount = fetchedPreview.filter(m => m.selected && !m.added).length;
  const addedCount = fetchedPreview.filter(m => m.added).length;
  summary.innerHTML = `共拉取 <b style="color:#fff;">${fetchedPreview.length}</b> 个模型 · 已选 <b style="color:var(--primary);">${selectedCount}</b> 个 · 已在列表中 <b style="color:var(--emerald);">${addedCount}</b> 个`;
}

function toggleAllFetched(value) {
  if (!assertEditable()) return;
  fetchedPreview.forEach(m => { if (!m.added) m.selected = value; });
  renderFetchPreview();
}

function commitFetchedModels() {
  if (!assertEditable()) return;
  const pid = syncCurrentFormToMemory();
  if (!pid) return alert('请先填写服务商 ID');
  const p = currentConfig.providers[pid];
  if (!p) return;
  const list = (p.models || []).slice();
  let addedCount = 0;
  fetchedPreview.forEach(m => {
    if (m.added) return;
    if (!m.selected) return;
    if (list.some(x => x.id === m.id)) return;
    const next = { id: m.id };
    // Apply alias if it's different from the id
    const trimmed = String(m.name || '').trim();
    if (trimmed && trimmed !== m.id) next.name = trimmed;
    list.push(next);
    m.added = true;
    m.selected = false;
    addedCount++;
  });
  p.models = list.sort((a, b) => a.id.localeCompare(b.id));
  renderModels(p.models);
  renderSidebar();
  renderFetchPreview();
  if (addedCount > 0) {
    setStatus(`✅ 已将 ${addedCount} 个模型添加到 [${pid}] 列表。点击「💾 保存」即可持久化`, '#10B981');
  } else {
    setStatus('没有选中可添加的模型，请先勾选', '#F59E0B');
  }
}

function closeFetchPreview() {
  fetchedPreview = [];
  const c = document.getElementById('fetchPreviewContainer');
  if (c) c.style.display = 'none';
}


function deleteCurrentProvider() {
  if (!assertEditable()) return;
  if (!selectedPid) return;
  if (!confirm(`确定删除服务商 [${selectedPid}] 吗？`)) return;
  delete currentConfig.providers[selectedPid];
  newProvider();
  saveAll();
}

async function saveAll() {
  if (!assertEditable()) return false;
  syncCurrentFormToMemory();
  setStatus('正在保存全局配置...', '#F59E0B');
  const res = await window.pywebview.api.save_config(currentConfig, currentConfigPath);
  if (res.success) {
    const countText = `${res.providerCount || 0} providers / ${res.modelCount || 0} models`;
    setStatus(`已保存到 models.json (${countText})。已打开的 Pi 会自动同步；若尚未生效，请先执行一次 /reload 加载 models-sync 扩展`, '#10B981');
    renderSidebar();
    return true;
  } else {
    setStatus('保存失败: ' + res.error, '#EF4444');
    return false;
  }
}

async function restartPi() {
  const saved = await saveAll();
  if (!saved) return;
  setStatus('正在启动新的 Pi 交互终端...', '#3B82F6');
  await window.pywebview.api.restart_pi();
  setStatus('已在新窗口启动 Pi，新窗口会读取最新配置', '#10B981');
}

function setStatus(msg, color = '#10B981') {
  const el = document.getElementById('statusMsg');
  el.innerText = '● ' + msg;
  el.style.color = color;
}

window.addEventListener('pywebviewready', () => {
  refreshTargets(false);
});
</script>
</body>
</html>
"""

def main():
    api = ApiBridge()
    window = webview.create_window(
        title="Pi模型配置",
        html=HTML_CONTENT,
        js_api=api,
        width=1120,
        height=720,
        min_size=(980, 620),
        frameless=True,
        easy_drag=True,
        background_color="#0F172A"
    )
    api.set_window(window)
    webview.start()

if __name__ == "__main__":
    main()
