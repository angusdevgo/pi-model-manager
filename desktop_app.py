import json
import os
import subprocess
import threading
import time
from datetime import datetime
import urllib.error
import urllib.request
import webview
from pathlib import Path

DEFAULT_AGENT_DIR = Path(os.environ.get("PI_CODING_AGENT_DIR", Path.home() / ".pi" / "agent"))
DEFAULT_MODELS_PATH = DEFAULT_AGENT_DIR / "models.json"
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
    if not isinstance(data, dict):
        return "pi-providers"
    return "pi-providers"

def read_config_file(path):
    raw = path.read_text(encoding="utf-8-sig")
    clean = strip_json_comments(raw).strip()
    if not clean:
        return {"providers": {}}
    return json.loads(clean)

def normalize_config_for_ui(path, data, schema):
    if isinstance(data, dict) and isinstance(data.get("providers"), dict):
        normalized = dict(data)
        normalized["providers"] = data.get("providers", {})
        return normalized
    return {"providers": {}}

def is_editable_schema(schema):
    return True

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

def sanitize_filename(name: str) -> str:
    text = str(name or "").strip()
    if not text:
        return "export"
    safe = []
    for ch in text:
        if ch.isalnum() or ch in ("-", "_", "."):
            safe.append(ch)
        else:
            safe.append("_")
    result = "".join(safe).strip("._")
    return result or "export"


def get_desktop_dir():
    desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
    return Path(desktop) if os.path.isdir(desktop) else Path.home()


def build_provider_export_text(provider_id, provider, source_path):
    provider = provider if isinstance(provider, dict) else {}
    display_name = provider.get("name") or provider_id
    base_url = provider.get("baseUrl") or ""
    api_key = provider.get("apiKey") or ""
    api_type = provider.get("api") or "openai-completions"
    models = provider.get("models") or []
    model_lines = []
    for model in models:
        if not isinstance(model, dict):
            continue
        model_id = str(model.get("id") or "").strip()
        if not model_id:
            continue
        model_name = str(model.get("name") or "").strip()
        if model_name and model_name != model_id:
            model_lines.append(f"- {model_id} ({model_name})")
        else:
            model_lines.append(f"- {model_id}")
    model_block = "\n".join(model_lines) if model_lines else "- (无模型)"
    key_text = api_key if api_key else "（空）"
    source_text = str(source_path) if source_path else ""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return (
        "Pi Model Manager 导出\n"
        f"导出时间: {timestamp}\n"
        f"配置文件: {source_text}\n"
        "\n"
        "服务商信息\n"
        f"显示名称: {display_name}\n"
        f"服务商 ID: {provider_id}\n"
        f"URL: {base_url}\n"
        f"Key: {key_text}\n"
        f"API类型: {api_type}\n"
        f"模型数量: {len(models)}\n"
        "\n"
        "模型列表\n"
        f"{model_block}\n"
    )


def build_all_providers_export_text(config, source_path):
    providers = config.get("providers") if isinstance(config, dict) else {}
    providers = providers if isinstance(providers, dict) else {}
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    source_text = str(source_path) if source_path else ""
    parts = [
        "Pi Model Manager 导出",
        f"导出时间: {timestamp}",
        f"配置文件: {source_text}",
        f"服务商数量: {len(providers)}",
        "",
    ]
    for idx, (provider_id, provider) in enumerate(providers.items(), start=1):
        if not isinstance(provider, dict):
            continue
        parts.append(f"[{idx}] {provider.get('name') or provider_id}")
        parts.append(f"服务商 ID: {provider_id}")
        parts.append(f"URL: {provider.get('baseUrl') or ''}")
        parts.append(f"Key: {provider.get('apiKey') or '（空）'}")
        parts.append(f"API类型: {provider.get('api') or 'openai-completions'}")
        models = provider.get('models') or []
        parts.append(f"模型数量: {len(models)}")
        if models:
            parts.append("模型列表:")
            for model in models:
                if not isinstance(model, dict):
                    continue
                mid = str(model.get('id') or '').strip()
                if not mid:
                    continue
                mname = str(model.get('name') or '').strip()
                parts.append(f"- {mid}" + (f" ({mname})" if mname and mname != mid else ""))
        else:
            parts.append("模型列表: - (无模型)")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def export_provider_txt(config, config_path, provider_id):
    if isinstance(config, str):
        config = json.loads(config)
    if not isinstance(config, dict):
        raise ValueError("配置数据无效")
    providers = config.get("providers") or {}
    provider = providers.get(provider_id)
    if not isinstance(provider, dict):
        raise ValueError("未找到当前服务商")
    text = build_provider_export_text(provider_id, provider, config_path)
    base_dir = get_desktop_dir()
    filename = sanitize_filename(provider.get("name") or provider_id) + "-export.txt"
    out_path = base_dir / filename
    out_path.write_text(text, encoding="utf-8")
    return out_path, text


def export_all_providers_txt(config, config_path):
    if isinstance(config, str):
        config = json.loads(config)
    if not isinstance(config, dict):
        raise ValueError("配置数据无效")
    text = build_all_providers_export_text(config, config_path)
    base_dir = get_desktop_dir()
    filename = sanitize_filename(Path(config_path).stem if config_path else "providers") + "-all-export.txt"
    out_path = base_dir / filename
    out_path.write_text(text, encoding="utf-8")
    return out_path, text


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
                if model.get("disabled") is True:
                    model["disabled"] = True
                else:
                    model.pop("disabled", None)
                model.pop("_failStreak", None)
                model.pop("_lastError", None)
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

def discover_config_targets():
    path = DEFAULT_MODELS_PATH.resolve()
    config = load_config(path)
    return [{
        "label": "Pi",
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


def test_model(base_url, api_key, api_type, model_id):
    """对单个模型发送最小化真实请求，验证 API 是否真正接通。
    返回: {success, latency_ms, error?}
    """
    base = (base_url or "").rstrip("/")
    if not base:
        return {"success": False, "error": "Base URL 为空"}
    start = time.time()
    try:
        if api_type == "anthropic-messages":
            endpoint = base + "/messages" if base.endswith("/v1") else base + "/v1/messages"
            headers = {"Content-Type": "application/json", "anthropic-version": "2023-06-01"}
            if api_key:
                headers["x-api-key"] = api_key
            body = {"model": model_id, "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]}
        elif api_type == "google-generative-ai":
            gbase = base
            if not gbase.endswith("/v1beta") and not gbase.endswith("/v1"):
                gbase = gbase + "/v1beta"
            endpoint = f"{gbase}/models/{model_id}:generateContent"
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["x-goog-api-key"] = api_key
            body = {"contents": [{"parts": [{"text": "hi"}]}]}
        elif api_type == "openai-responses":
            endpoint = base + "/responses" if base.endswith("/v1") else base + "/v1/responses"
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            body = {"model": model_id, "input": "hi", "max_output_tokens": 1}
        else:  # openai-completions (默认)
            endpoint = base + "/chat/completions" if base.endswith("/v1") else base + "/v1/chat/completions"
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            body = {"model": model_id, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}

        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp.read()
        latency_ms = int((time.time() - start) * 1000)
        return {"success": True, "latency_ms": latency_ms, "model": model_id}
    except urllib.error.HTTPError as e:
        latency_ms = int((time.time() - start) * 1000)
        detail = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(err_body)
                detail = str(parsed.get("error", parsed))[:220]
            except Exception:
                detail = err_body[:220]
        except Exception:
            pass
        return {"success": False, "status": e.code, "error": f"HTTP {e.code}: {detail}", "latency_ms": latency_ms}
    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        return {"success": False, "error": str(e)[:220], "latency_ms": latency_ms}

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
        return {"config": load_config(config_path), "path": str(config_path), "schema": schema, "editable": editable, "selectedProviderId": getattr(self, '_last_selected_provider', None)}

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

    def test_model(self, base_url, api_key, api_type, model_id):
        try:
            return test_model(base_url, api_key, api_type, model_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_provider_txt(self, config_json_str, path, provider_id):
        try:
            config_path = normalize_config_path(path)
            data = json.loads(config_json_str) if isinstance(config_json_str, str) else config_json_str
            out_path, text = export_provider_txt(data, config_path, provider_id)
            return {"success": True, "path": str(out_path), "content": text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_all_providers_txt(self, config_json_str, path):
        try:
            config_path = normalize_config_path(path)
            data = json.loads(config_json_str) if isinstance(config_json_str, str) else config_json_str
            out_path, text = export_all_providers_txt(data, config_path)
            return {"success": True, "path": str(out_path), "content": text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_current_provider(self):
        try:
            config_path = normalize_config_path(None)
            data = load_config(config_path)
            provider_id = getattr(self, '_last_selected_provider', None)
            if not provider_id:
                return {"success": False, "error": "请先选择一个服务商"}
            out_path, text = export_provider_txt(data, config_path, provider_id)
            return {"success": True, "path": str(out_path), "content": text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def set_selected_provider(self, provider_id):
        self._last_selected_provider = provider_id
        return {"success": True}

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
<title>模型配置</title>
<style>
  :root {
    --b-bg: #0B0E13;
    --b-bg-2: #11151C;
    --b-surface: #161B23;
    --b-surface-2: #1D232D;
    --b-line: #262C36;
    --b-line-2: #2F3744;
    --b-text: #F5F5F4;
    --b-text-2: #B8BCC4;
    --b-text-3: #6B7280;
    --b-text-4: #4B5260;
    --b-accent: #E64A2E;
    --b-accent-2: #FF7A5C;
    --b-accent-soft: rgba(230, 74, 46, 0.14);
    --b-blue: #3B82F6;
    --b-green: #10B981;
    --b-amber: #F59E0B;
    --s-gold: #C8962C;
    --b-serif: "Noto Serif SC", "Songti SC", serif;
    --b-sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
    --b-mono: "JetBrains Mono", "Cascadia Code", "Consolas", "SF Mono", monospace;

    /* 兼容旧变量名并映射到屎山黑橙美学 */
    --card-bg: #161B23;
    --card-hover: #1D232D;
    --glass-border: #262C36;
    --glass-border-focus: #E64A2E;
    --input-bg: #11151C;
    --primary: #E64A2E;
    --primary-hover: #FF7A5C;
    --primary-glow: rgba(230, 74, 46, 0.25);
    --emerald: #10B981;
    --emerald-hover: #059669;
    --emerald-glow: rgba(16, 185, 129, 0.25);
    --rose: #E64A2E;
    --rose-hover: #DC2626;
    --amber: #F59E0B;
    --indigo: #6366F1;
    --text-main: #F5F5F4;
    --text-muted: #B8BCC4;
    --text-dim: #6B7280;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: var(--b-sans); user-select: none; }
  body { font-size: 13.5px; line-height: 1.45; }
  
  ::-webkit-scrollbar { width: 5px; height: 5px; }
  ::-webkit-scrollbar-track { background: var(--b-bg); }
  ::-webkit-scrollbar-thumb { background: var(--b-line-2); border-radius: 2px; }
  ::-webkit-scrollbar-thumb:hover { background: var(--b-text-3); }

  body {
    background-color: var(--b-bg);
    background-image: radial-gradient(circle at 20% 0%, rgba(230, 74, 46, 0.05), transparent 50%), linear-gradient(180deg, var(--b-bg) 0%, var(--b-bg-2) 100%);
    color: var(--b-text);
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border: 1px solid var(--b-line);
    border-radius: 4px;
  }
  
  /* 顶部现代化标题栏 (屎山 topbar 风格) */
  header {
    background: rgba(11, 14, 19, 0.92);
    backdrop-filter: blur(20px);
    border-bottom: 1px solid var(--b-line);
    padding: 0 20px;
    height: 56px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-shrink: 0;
  }
  .pywebview-drag-region { -webkit-app-region: drag; }
  .pywebview-no-drag-region { -webkit-app-region: no-drag; }

  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;
    min-width: 0;
    flex: 1;
  }
  .header-right { display: flex; align-items: center; gap: 12px; flex-shrink: 0; }

  .logo-title {
    font-family: var(--b-serif);
    font-weight: 700;
    font-size: 16px;
    letter-spacing: 1.5px;
    color: var(--b-text);
    display: flex;
    align-items: center;
    gap: 10px;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .logo-title .brand-mark {
    width: 28px;
    height: 28px;
    background: var(--b-accent);
    display: grid;
    place-items: center;
    font-family: var(--b-serif);
    font-size: 14px;
    color: #fff;
    font-weight: 900;
    border-radius: 2px;
    box-shadow: 0 0 10px rgba(230, 74, 46, 0.35);
  }
  .logo-title .sub-en {
    font-family: var(--b-mono);
    font-size: 9px;
    font-weight: 500;
    letter-spacing: 0.16em;
    color: var(--b-text-3);
    text-transform: uppercase;
  }
  
  /* 顶部一体化分段标签栏 (Segmented Tabs) */
  .target-tabs {
    display: flex;
    align-items: center;
    background: var(--b-surface);
    border: 1px solid var(--b-line);
    border-radius: 4px;
    padding: 2px;
    gap: 2px;
    box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.3);
  }
  .target-tab-item {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 3px;
    cursor: pointer;
    font-family: var(--b-mono);
    font-size: 12px;
    font-weight: 500;
    color: var(--b-text-3);
    transition: all 0.15s ease;
    user-select: none;
    border: 1px solid transparent;
  }
  .target-tab-item:hover {
    color: var(--b-text);
    background: var(--b-surface-2);
  }
  .target-tab-item.active {
    background: var(--b-surface-2);
    color: #FFFFFF;
    font-weight: 700;
    border-color: var(--b-line-2);
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
    position: relative;
  }
  .target-tab-item.active::before {
    content: '';
    position: absolute;
    bottom: -2px;
    left: 20%;
    right: 20%;
    height: 2px;
    background: var(--b-accent);
    border-radius: 1px;
    box-shadow: 0 0 6px var(--b-accent);
  }
  .target-tab-item .tab-icon {
    font-size: 12px;
    opacity: 0.8;
  }
  .target-tab-item.active .tab-icon {
    opacity: 1;
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-shrink: 0;
  }

  .header-actions {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  /* 窗口控制三键 */
  .window-controls {
    display: flex;
    align-items: center;
    margin-left: 6px;
    border-left: 1px solid var(--b-line);
    padding-left: 8px;
    gap: 2px;
  }
  .win-btn {
    width: 28px;
    height: 28px;
    border-radius: 2px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    color: var(--b-text-3);
    font-size: 12px;
    transition: all 0.15s ease;
  }
  .win-btn:hover {
    background: var(--b-surface-2);
    color: var(--b-text);
  }
  .win-btn.close:hover {
    background: var(--b-accent);
    color: white;
  }

  .btn {
    font-family: var(--b-sans);
    border: 1px solid var(--b-line-2);
    border-radius: 2px;
    padding: 6px 14px;
    font-size: 12.5px;
    font-weight: 500;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    white-space: nowrap;
    transition: all 0.12s ease;
    background: var(--b-surface);
    color: var(--b-text);
  }
  .btn:hover {
    border-color: var(--b-accent);
    color: var(--b-accent);
    background: var(--b-surface-2);
  }
  .btn .shortcut-badge {
    font-family: var(--b-mono);
    font-size: 9.5px;
    letter-spacing: 0.05em;
    opacity: 0.85;
    background: rgba(0, 0, 0, 0.35);
    padding: 1px 5px;
    border-radius: 2px;
    color: var(--b-text-2);
    border: 1px solid var(--b-line);
  }
  .btn-primary {
    background: var(--b-accent);
    border-color: var(--b-accent);
    color: #FFF !important;
  }
  .btn-primary:hover {
    background: var(--b-accent-2);
    border-color: var(--b-accent-2);
    color: #FFF !important;
    box-shadow: 0 0 12px rgba(230, 74, 46, 0.4);
  }
  .btn-emerald {
    background: var(--b-surface-2);
    border-color: rgba(16, 185, 129, 0.4);
    color: #6EE7B7;
  }
  .btn-emerald:hover {
    border-color: var(--b-green);
    background: rgba(16, 185, 129, 0.14);
    color: #A7F3D0;
  }
  .btn-indigo {
    background: var(--b-surface-2);
    border-color: rgba(99, 102, 241, 0.4);
    color: #A5B4FC;
  }
  .btn-indigo:hover {
    border-color: #818CF8;
    background: rgba(99, 102, 241, 0.14);
    color: #C7D2FE;
  }
  .btn-rose {
    background: var(--b-surface-2);
    border-color: rgba(230, 74, 46, 0.35);
    color: #FFA39E;
  }
  .btn-rose:hover {
    border-color: var(--b-accent);
    background: var(--b-accent-soft);
    color: #FFCCC7;
  }
  .btn-secondary {
    background: var(--b-surface);
    color: var(--b-text);
    border: 1px solid var(--b-line-2);
  }
  .btn-secondary:hover {
    background: var(--b-surface-2);
    border-color: var(--b-text-3);
  }
  .btn-ghost {
    background: transparent;
    border: 1px solid transparent;
    color: var(--b-text-3);
    padding: 4px 8px;
  }
  .btn-ghost:hover {
    background: var(--b-accent-soft);
    color: var(--b-accent);
    border-color: transparent;
  }

  /* 三栏工作台平铺布局 */
  .layout {
    display: flex;
    flex: 1;
    overflow: hidden;
    background: var(--b-bg);
  }
  
  /* 栏目1: 左侧服务商列表 (固定宽度 240px) */
  .sidebar {
    width: 240px;
    min-width: 220px;
    background: var(--b-surface);
    border-right: 1px solid var(--b-line);
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
  }
  .sidebar-header {
    padding: 10px 14px;
    border-bottom: 1px solid var(--b-line);
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-family: var(--b-serif);
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.5px;
    color: var(--b-text);
  }
  .sidebar-search {
    padding: 8px 10px;
    border-bottom: 1px solid var(--b-line);
    background: var(--b-bg);
  }
  .search-input {
    width: 100%;
    background: var(--b-surface);
    border: 1px solid var(--b-line);
    border-radius: 2px;
    padding: 5px 8px;
    color: var(--b-text);
    font-family: var(--b-sans);
    font-size: 12px;
    outline: none;
    transition: border-color 0.15s;
  }
  .search-input:focus {
    border-color: var(--b-accent);
  }
  .search-input::placeholder { color: var(--b-text-4); }

  .provider-list {
    flex: 1;
    overflow-y: auto;
    padding: 6px;
    display: flex;
    flex-direction: column;
    gap: 3px;
    background: var(--b-bg);
  }
  
  .p-card {
    background: var(--b-surface);
    border: 1px solid var(--b-line);
    border-radius: 2px;
    padding: 8px 10px;
    cursor: pointer;
    transition: all 0.12s ease;
    position: relative;
  }
  .p-card:hover {
    border-color: var(--b-line-2);
    background: var(--b-surface-2);
  }
  .p-card.active {
    border-color: var(--b-line-2);
    border-left: 3px solid var(--b-accent);
    background: var(--b-surface-2);
  }
  .p-card-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px; }
  .p-name { font-weight: 600; font-size: 12.5px; color: var(--b-text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 130px; }
  .p-id { font-size: 11px; color: var(--b-text-3); font-family: var(--b-mono); }
  .p-badges { display: flex; align-items: center; gap: 4px; }
  .p-count { font-family: var(--b-mono); font-size: 10px; background: var(--b-bg); padding: 1px 5px; border-radius: 2px; color: var(--b-text-2); border: 1px solid var(--b-line); }
  .p-proto { font-family: var(--b-mono); font-size: 9px; padding: 1px 4px; border-radius: 2px; background: rgba(230, 74, 46, 0.12); color: var(--b-accent-2); border: 1px solid rgba(230, 74, 46, 0.25); text-transform: uppercase; }

  /* 栏目2: 中间服务商连接配置 (固定 310px) */
  .column-provider {
    width: 310px;
    min-width: 290px;
    background: var(--b-surface);
    border-right: 1px solid var(--b-line);
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    padding: 16px 16px;
    flex-shrink: 0;
    gap: 12px;
  }

  /* 栏目3: 右侧模型管理与测活 (自适应填满) */
  .column-models {
    flex: 1;
    min-width: 380px;
    background: var(--b-bg-2);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    padding: 16px 20px;
    gap: 12px;
  }

  .card {
    background: var(--b-surface);
    border: 1px solid var(--b-line);
    border-radius: 2px;
    padding: 14px 16px;
    position: relative;
  }
  .card-title {
    font-family: var(--b-serif);
    font-size: 13.5px;
    font-weight: 600;
    letter-spacing: 0.5px;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    color: var(--b-text);
    border-bottom: 1px solid var(--b-line);
    padding-bottom: 8px;
  }
  .card-title .title-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .card-title .count-badge {
    font-family: var(--b-mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 2px 6px;
    border-radius: 2px;
    background: var(--b-bg);
    color: var(--b-text-3);
    border: 1px solid var(--b-line);
  }

  /* 表单查看模式 (View Mode) 工业数据条 */
  .view-panel {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .view-field {
    display: flex;
    flex-direction: column;
    gap: 2px;
    border-bottom: 1px dashed var(--b-line);
    padding-bottom: 6px;
  }
  .view-field:last-child { border-bottom: none; padding-bottom: 0; }
  .view-label {
    font-family: var(--b-mono);
    font-size: 9.5px;
    letter-spacing: 0.08em;
    color: var(--b-text-4);
    text-transform: uppercase;
  }
  .view-value {
    font-family: var(--b-mono);
    font-size: 12px;
    color: var(--b-text);
    word-break: break-all;
    user-select: text;
    line-height: 1.4;
  }
  .view-value.empty {
    color: var(--b-text-4);
    font-style: italic;
  }

  /* 表单编辑模式 (Edit Mode) */
  .edit-panel {
    display: none;
    flex-direction: column;
    gap: 10px;
  }
  
  .form-group { display: flex; flex-direction: column; gap: 4px; position: relative; }
  .form-group label { font-family: var(--b-mono); font-size: 10px; letter-spacing: 0.06em; font-weight: 500; color: var(--b-text-3); display: flex; align-items: center; gap: 4px; text-transform: uppercase; }
  .input-wrapper { position: relative; display: flex; align-items: center; }
  .input-wrapper .input { width: 100%; }
  .input-wrapper .toggle-pwd {
    position: absolute;
    right: 6px;
    cursor: pointer;
    color: var(--b-text-3);
    font-size: 12px;
    padding: 2px;
    border-radius: 2px;
    transition: color 0.15s;
  }
  .input-wrapper .toggle-pwd:hover { color: var(--b-text); background: var(--b-surface-2); }

  .input {
    background: var(--b-bg);
    border: 1px solid var(--b-line);
    border-radius: 2px;
    padding: 6px 9px;
    color: var(--b-text);
    font-family: var(--b-mono);
    font-size: 12px;
    outline: none;
    user-select: text;
    transition: border-color 0.15s;
  }
  .input:focus {
    border-color: var(--b-accent);
  }
  select.input {
    cursor: pointer;
    font-family: var(--b-sans);
  }
  select.input option {
    background-color: #161B23 !important;
    color: #F5F5F4 !important;
    padding: 6px 10px;
  }

  /* 模型工作区顶部分段导航 (Models Tab / Fetch Tab) */
  .model-work-tabs {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 8px;
    flex-shrink: 0;
    flex-wrap: wrap;
  }
  .model-tab-buttons {
    display: inline-flex;
    background: var(--b-surface);
    border: 1px solid var(--b-line);
    border-radius: 4px;
    padding: 2px;
    gap: 2px;
  }
  .model-tab-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 3px;
    cursor: pointer;
    font-family: var(--b-mono);
    font-size: 12px;
    font-weight: 500;
    color: var(--b-text-3);
    border: 1px solid transparent;
    transition: all 0.15s ease;
    user-select: none;
  }
  .model-tab-btn:hover {
    color: var(--b-text);
    background: var(--b-surface-2);
  }
  .model-tab-btn.active {
    background: var(--b-surface-2);
    color: #FFFFFF;
    font-weight: 700;
    border-color: var(--b-line-2);
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
    position: relative;
  }
  .model-tab-btn.active::before {
    content: '';
    position: absolute;
    bottom: -2px;
    left: 20%;
    right: 20%;
    height: 2px;
    background: var(--b-accent);
    border-radius: 1px;
  }
  .model-tab-badge {
    font-size: 10px;
    padding: 1px 5px;
    border-radius: 10px;
    background: var(--b-line);
    color: var(--b-text-2);
  }
  .model-tab-btn.active .model-tab-badge {
    background: var(--b-accent-soft);
    color: var(--b-accent-2);
  }

  /* 模型视图容器 */
  .model-view-pane {
    display: none;
    flex-direction: column;
    flex: 1;
    overflow: hidden;
    min-height: 0;
  }
  .model-view-pane.active {
    display: flex;
  }

  /* 模型列表容器 - 弹性撑满并支持滚动 */
  .model-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    flex-shrink: 0;
  }
  .model-add-bar {
    display: flex;
    gap: 6px;
    background: var(--b-surface);
    padding: 6px;
    border-radius: 2px;
    border: 1px solid var(--b-line);
    flex-shrink: 0;
    align-items: center;
  }
  .model-add-bar .input {
    min-width: 0;
  }
  .model-add-bar .btn {
    flex-shrink: 0;
    white-space: nowrap;
    padding: 6px 12px;
  }
  .models-tag-container {
    display: flex;
    flex-direction: column;
    gap: 4px;
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 6px;
    background: var(--b-surface);
    border-radius: 2px;
    border: 1px solid var(--b-line);
    min-height: 0;
  }

  /* 定时测活下拉与健康状态 */
  .schedule-wrap { position: relative; }
  .schedule-dropdown {
    position: absolute;
    top: calc(100% + 6px);
    right: 0;
    min-width: 180px;
    padding: 10px;
    background: var(--b-surface);
    border: 1px solid var(--b-line-2);
    border-radius: 2px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.6);
    z-index: 999;
  }
  .schedule-dropdown-title { font-family: var(--b-mono); font-size: 10px; color: var(--b-text-4); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.1em; }
  .schedule-option { display: flex; align-items: center; gap: 8px; padding: 5px 6px; border-radius: 2px; cursor: pointer; font-size: 12px; color: var(--b-text); transition: background 0.12s; }
  .schedule-option:hover { background: var(--b-surface-2); }
  .schedule-option input[type="radio"] { accent-color: var(--b-accent); cursor: pointer; }
  .schedule-status { margin-top: 6px; padding: 6px 8px; font-family: var(--b-mono); font-size: 11px; color: var(--b-text-3); background: var(--b-bg); border-radius: 2px; border: 1px solid var(--b-line); line-height: 1.4; }
  .schedule-status.active { color: var(--b-accent-2); border-color: rgba(230, 74, 46, 0.4); background: var(--b-accent-soft); }
  .schedule-divider { height: 1px; background: var(--b-line); margin: 8px 0; }

  #scheduleBtn.active { color: var(--b-accent-2); border-color: var(--b-accent); background: var(--b-accent-soft); }
  #scheduleBtn.active::before { content: '●'; color: var(--b-accent); margin-right: 4px; animation: pulse 1.6s ease-in-out infinite; }

  .health-summary { display: inline-flex; align-items: center; gap: 5px; margin-left: 4px; }
  .health-pill {
    display: inline-flex; align-items: center; gap: 3px;
    font-family: var(--b-mono);
    font-size: 10.5px; font-weight: 600;
    padding: 1px 6px;
    border-radius: 2px;
    border: 1px solid transparent;
  }
  .health-pill.ok { background: rgba(16, 185, 129, 0.14); color: #6EE7B7; border-color: rgba(16, 185, 129, 0.35); }
  .health-pill.fail { background: rgba(230, 74, 46, 0.14); color: #FFA39E; border-color: rgba(230, 74, 46, 0.35); }
  .health-meta { font-family: var(--b-mono); font-size: 10px; color: var(--b-text-4); margin-left: 4px; }
  .health-meta.testing { color: var(--b-amber); }

  .model-tag.testing-all {
    border-color: var(--b-accent);
    background: var(--b-accent-soft);
  }
  .model-tag {
    display: flex;
    align-items: center;
    gap: 6px;
    background: var(--b-surface);
    border: 1px solid var(--b-line);
    border-radius: 2px;
    padding: 5px 8px;
    font-size: 12px;
    transition: all 0.12s ease;
    min-width: 0;
  }
  .model-tag:hover {
    border-color: var(--b-line-2);
    background: var(--b-surface-2);
  }
  .model-tag .alias-icon { font-size: 11px; flex-shrink: 0; opacity: 0.6; color: var(--b-text-3); }
  .model-tag .alias-input {
    background: transparent;
    border: 1px dashed transparent;
    border-radius: 2px;
    color: var(--b-text);
    font-size: 12px;
    font-weight: 500;
    flex: 1;
    min-width: 70px;
    max-width: 160px;
    padding: 2px 4px;
    outline: none;
    font-family: inherit;
    transition: all 0.12s;
  }
  .model-tag .alias-input:hover { border-color: var(--b-line-2); background: var(--b-bg); }
  .model-tag .alias-input:focus { border-color: var(--b-accent); background: var(--b-bg); }
  .model-tag .alias-id {
    font-family: var(--b-mono);
    font-size: 11px;
    color: var(--b-text-3);
    flex: 1.2;
    min-width: 60px;
    background: var(--b-bg);
    padding: 2px 6px;
    border-radius: 2px;
    border: 1px solid var(--b-line);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .model-tag .del-btn {
    cursor: pointer;
    color: var(--b-text-4);
    font-size: 12px;
    padding: 1px 4px;
    border-radius: 2px;
    flex-shrink: 0;
    transition: all 0.12s;
  }
  .model-tag .del-btn:hover { color: #FFF; background: var(--b-accent); }
  .model-tag .test-btn, .fetch-row .test-btn {
    cursor: pointer;
    font-size: 11px;
    flex-shrink: 0;
    padding: 2px 5px;
    border-radius: 2px;
    border: 1px solid var(--b-line);
    background: var(--b-bg);
    color: var(--b-text-3);
    transition: all 0.12s;
    user-select: none;
    white-space: nowrap;
  }
  .model-tag .test-btn:hover, .fetch-row .test-btn:hover {
    border-color: var(--b-accent);
    color: var(--b-accent);
    background: var(--b-accent-soft);
  }
  .model-tag .test-btn.testing, .fetch-row .test-btn.testing { opacity: 0.6; }
  .model-tag .test-btn.ok, .fetch-row .test-btn.ok { color: #6EE7B7; background: rgba(16, 185, 129, 0.14); border-color: rgba(16, 185, 129, 0.4); }
  .model-tag .test-btn.fail, .fetch-row .test-btn.fail { color: #FFA39E; background: rgba(230, 74, 46, 0.14); border-color: rgba(230, 74, 46, 0.4); }

  /* 模型禁用状态 */
  .model-tag.disabled { opacity: 0.45; background: var(--b-bg); border-style: dashed; }
  .model-tag.disabled .alias-input { color: var(--b-text-4); text-decoration: line-through; }
  .model-tag.disabled .alias-id { color: var(--b-text-4); }
  .disabled-badge {
    font-family: var(--b-mono); font-size: 9.5px; font-weight: 600; padding: 1px 5px; border-radius: 2px;
    background: rgba(230, 74, 46, 0.15); color: #FFA39E; border: 1px solid rgba(230, 74, 46, 0.35);
    flex-shrink: 0; text-transform: uppercase;
  }
  .fail-streak {
    font-family: var(--b-mono); font-size: 9.5px; font-weight: 600; padding: 1px 5px; border-radius: 2px;
    background: rgba(245, 158, 11, 0.15); color: #FCD34D; border: 1px solid rgba(245, 158, 11, 0.35);
    flex-shrink: 0;
  }
  .model-tag .toggle-btn {
    cursor: pointer; font-size: 11px; padding: 1px 5px; border-radius: 2px;
    border: 1px solid var(--b-line); background: var(--b-bg); transition: all 0.12s; flex-shrink: 0;
  }
  .model-tag .toggle-btn.off { opacity: 0.6; color: var(--b-text-3); }
  .model-tag .toggle-btn.off:hover { opacity: 1; border-color: var(--b-amber); color: var(--b-amber); }
  .model-tag .toggle-btn.on { color: #FFA39E; border-color: rgba(230, 74, 46, 0.4); background: var(--b-accent-soft); }
  .model-tag .toggle-btn.on:hover { color: #6EE7B7; border-color: rgba(16, 185, 129, 0.4); background: rgba(16, 185, 129, 0.14); }

  /* 拉取预览容器 (全幅视图) */
  .fetch-preview-container {
    display: flex;
    flex-direction: column;
    flex: 1;
    background: var(--b-surface);
    border-radius: 2px;
    border: 1px solid var(--b-line);
    padding: 10px;
    overflow: hidden;
    min-height: 0;
  }
  .fetch-preview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    gap: 8px;
    flex-wrap: wrap;
    flex-shrink: 0;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--b-line);
  }
  .fetch-preview-header .title {
    font-family: var(--b-sans);
    color: var(--b-text);
    font-size: 13px;
    font-weight: 700;
  }
  .fetch-preview-header .actions { display: flex; gap: 4px; flex-wrap: wrap; align-items: center; }
  .fetch-preview-header .actions .btn { padding: 4px 9px; font-size: 11px; border-radius: 2px; white-space: nowrap; flex-shrink: 0; }
  .fetch-preview-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding-right: 2px;
    min-height: 0;
  }
  .fetch-row {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    background: var(--b-surface);
    border: 1px solid var(--b-line);
    border-radius: 2px;
    transition: all 0.12s;
    min-width: 0;
  }
  .fetch-row:hover { background: var(--b-bg); border-color: var(--b-line-2); }
  .fetch-row.added { opacity: 0.45; background: var(--b-bg); border-style: dashed; }
  .fetch-row .checkbox { width: 13px; height: 13px; cursor: pointer; flex-shrink: 0; accent-color: var(--b-accent); margin: 0; }
  .fetch-row .model-id {
    font-family: var(--b-mono);
    font-size: 11px;
    color: var(--b-text-2);
    flex: 1.1;
    min-width: 80px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    background: var(--b-bg);
    padding: 2px 5px;
    border-radius: 2px;
    border: 1px solid var(--b-line);
  }
  .fetch-row .alias-input {
    flex: 1;
    min-width: 60px;
    max-width: 140px;
    background: var(--b-bg);
    border: 1px solid var(--b-line);
    border-radius: 2px;
    color: var(--b-text);
    font-size: 11.5px;
    padding: 2px 6px;
    outline: none;
    font-family: inherit;
    transition: border-color 0.12s;
  }
  .fetch-row .alias-input:focus { border-color: var(--b-accent); }
  .fetch-row .alias-input::placeholder { color: var(--b-text-4); font-size: 11px; }
  .fetch-row .status-badge {
    font-family: var(--b-mono);
    font-size: 9.5px;
    padding: 1px 5px;
    border-radius: 2px;
    background: rgba(16, 185, 129, 0.12);
    color: #6EE7B7;
    flex-shrink: 0;
    border: 1px solid rgba(16, 185, 129, 0.3);
    white-space: nowrap;
  }
  .fetch-summary {
    font-family: var(--b-mono);
    font-size: 11px;
    color: var(--b-text-3);
    padding: 3px 6px;
    background: var(--b-bg);
    border-radius: 2px;
    border: 1px solid var(--b-line);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* 底部状态栏 */
  footer {
    background: var(--b-surface);
    border-top: 1px solid var(--b-line);
    padding: 6px 18px;
    font-size: 11.5px;
    color: var(--b-text-3);
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-shrink: 0;
  }
  footer .footer-left { display: flex; align-items: center; gap: 8px; font-family: var(--b-mono); }
  footer .footer-right { display: flex; align-items: center; gap: 14px; font-family: var(--b-mono); font-size: 10.5px; color: var(--b-text-4); }
  footer .footer-right kbd { background: var(--b-bg); color: var(--b-text-2); padding: 1px 5px; border-radius: 2px; border: 1px solid var(--b-line); font-family: var(--b-mono); }

</style>
</head>
<body>

<header class="pywebview-drag-region">
  <div class="header-left pywebview-no-drag-region">
    <div class="logo-title pywebview-drag-region" title="按住这里拖动窗口">
      <div class="brand-mark">配</div>
      <div style="display: flex; flex-direction: column; line-height: 1.1;">
        <span>模型配置</span>
        <span class="sub-en">MODEL CONFIG MANAGER</span>
      </div>
    </div>
    <div class="target-tabs pywebview-no-drag-region" id="targetTabs" title="切换 Agent 配置文件"></div>
  </div>

  <div class="header-right pywebview-no-drag-region">
    <div class="header-actions pywebview-no-drag-region">
      <button class="btn btn-primary" id="saveBtn" onclick="saveAll()" title="保存全局配置到文件 (快捷键: Ctrl+S)">
        <span>💾 保存</span>
      </button>
      <button class="btn btn-secondary" onclick="exportAllProviders()" title="导出全部服务商为 TXT，包含显示名称、URL 和 Key">
        <span>📦 导出全部</span>
      </button>
      <button class="btn btn-emerald" onclick="restartPi()" title="保存配置并在新终端中启动 Pi 会话">
        <span>🔄 重启</span>
      </button>
    </div>
    
    <div class="window-controls pywebview-no-drag-region">
      <div class="win-btn" title="最小化" onclick="window.pywebview.api.minimize_window()">—</div>
      <div class="win-btn" title="最大化/还原" onclick="window.pywebview.api.maximize_window()">▢</div>
      <div class="win-btn close" title="关闭" onclick="window.pywebview.api.close_window()">✕</div>
    </div>
  </div>
</header>

<div class="layout">
  <!-- 栏目1: 服务商导航栏 -->
  <div class="sidebar">
    <div class="sidebar-header">
      <span>已配置服务商</span>
      <button class="btn btn-secondary edit-action" style="padding: 2px 7px; font-size: 11px;" onclick="newProvider()">➕ 新建</button>
    </div>
    <div class="sidebar-search">
      <input class="search-input" id="providerSearch" placeholder="🔍 搜索服务商..." oninput="renderSidebar()">
    </div>
    <div class="provider-list" id="providerList"></div>
  </div>

  <!-- 栏目2: 服务商连接与认证面板 (支持查看/锁定与编辑模式) -->
  <div class="column-provider">
    <div class="card" style="display: flex; flex-direction: column; gap: 12px; height: 100%;">
      <div class="card-title">
        <div class="title-left">
          <span>🛠️ 服务商连接 (Provider)</span>
        </div>
        <div id="providerModeActions" style="display: flex; gap: 6px;">
          <button class="btn btn-secondary edit-action" id="editProviderBtn" onclick="toggleProviderEditMode(true)" title="解锁并编辑服务商连接参数">✏️ 编辑</button>
          <button class="btn btn-primary edit-action" id="saveProviderBtn" style="display: none;" onclick="saveProviderEdit()" title="保存修改并锁定">✓ 完成</button>
          <button class="btn btn-ghost edit-action" id="cancelProviderBtn" style="display: none;" onclick="cancelProviderEdit()" title="取消修改">✕ 取消</button>
        </div>
      </div>

      <!-- 查看模式: 紧凑工业数据面板 -->
      <div class="view-panel" id="providerViewPanel">
        <div class="view-field">
          <span class="view-label">服务商 ID</span>
          <span class="view-value" id="vId">-</span>
        </div>
        <div class="view-field">
          <span class="view-label">显示名称</span>
          <span class="view-value" id="vName">-</span>
        </div>
        <div class="view-field">
          <span class="view-label">Base URL 端点</span>
          <span class="view-value" id="vBaseUrl">-</span>
        </div>
        <div class="view-field">
          <span class="view-label">API 密钥 (Key)</span>
          <div style="display: flex; align-items: center; justify-content: space-between;">
            <span class="view-value" id="vApiKey" style="letter-spacing: 0.05em;">-</span>
            <button class="btn btn-ghost" style="padding: 1px 4px; font-size: 11px;" onclick="toggleViewKeyMask()" id="viewMaskBtn" title="显隐 API Key">👁️</button>
          </div>
        </div>
        <div class="view-field">
          <span class="view-label">协议类型</span>
          <span class="view-value" id="vApi">-</span>
        </div>
      </div>

      <!-- 编辑模式: 高对比度暗色输入表单 -->
      <div class="edit-panel" id="providerEditPanel">
        <div class="form-group">
          <label>服务商 ID <span style="color: var(--b-accent);">*</span></label>
          <input class="input" id="pId" placeholder="例如: deepseek, grok, openrouter">
        </div>
        <div class="form-group">
          <label>显示名称 (可选)</label>
          <input class="input" id="pName" placeholder="例如: DeepSeek Official">
        </div>
        <div class="form-group">
          <label>Base URL <span style="color: var(--b-accent);">*</span></label>
          <input class="input" id="pBaseUrl" placeholder="例如: https://api.deepseek.com/v1">
        </div>
        <div class="form-group">
          <label>API Key</label>
          <div class="input-wrapper">
            <input class="input" type="password" id="pApiKey" placeholder="sk-...">
            <span class="toggle-pwd" id="toggleApiKeyBtn" onclick="toggleApiKeyVisibility()" title="显示/隐藏 API Key">👁️</span>
          </div>
        </div>
        <div class="form-group">
          <label>API 协议类型</label>
          <select class="input" id="pApi" onchange="syncCurrentFormToMemory(); renderSidebar();">
            <option value="openai-completions">openai-completions (OpenAI 补全)</option>
            <option value="openai-responses">openai-responses (OpenAI Responses)</option>
            <option value="anthropic-messages">anthropic-messages (Claude 原生)</option>
            <option value="google-generative-ai">google-generative-ai (Gemini 原生)</option>
          </select>
        </div>
      </div>

      <div style="margin-top: auto; padding-top: 12px; border-top: 1px solid var(--b-line); display: flex; flex-direction: column; gap: 8px;">
        <button class="btn btn-emerald edit-action" style="width: 100%;" onclick="fetchRemoteModels()">🔄 自动拉取远程模型</button>
        <button class="btn btn-secondary edit-action" style="width: 100%;" onclick="exportCurrentProvider()" title="导出当前服务商信息（含名称、URL、Key 与模型）为 TXT 文件">📤 导出当前服务商</button>
        <button class="btn btn-rose edit-action" style="width: 100%;" onclick="deleteCurrentProvider()" title="删除当前服务商并立即保存">🗑️ 删除服务商</button>
      </div>
    </div>
  </div>

  <!-- 栏目3: 模型管理与测活工作区 (分段 Tab 视图，彻底消除遮挡) -->
  <div class="column-models">
    <div class="card" style="display: flex; flex-direction: column; height: 100%; overflow: hidden; padding: 12px 14px;">
      
      <!-- 顶部分段切换导航 -->
      <div class="model-work-tabs">
        <div class="model-tab-buttons">
          <div class="model-tab-btn active" id="tabBtnModels" onclick="switchModelWorkTab('models')">
            <span>📋 已配置模型</span>
            <span class="model-tab-badge" id="modelsTabBadge">0</span>
          </div>
          <div class="model-tab-btn" id="tabBtnFetch" onclick="switchModelWorkTab('fetch')">
            <span>📥 拉取预览</span>
            <span class="model-tab-badge" id="fetchTabBadge" style="display: none;">0</span>
          </div>
        </div>

        <div style="display: flex; gap: 6px; align-items: center;">
          <input class="search-input" id="modelSearch" style="width: 130px;" placeholder="🔍 过滤模型/别名..." oninput="renderModels()">
          <button class="btn btn-indigo edit-action" id="testAllBtn" onclick="testAllModels()" title="依次测活当前服务商的全部模型">⚡ 全部测活</button>
          <div class="schedule-wrap" title="设置定时自动测活">
            <button class="btn btn-ghost" id="scheduleBtn" onclick="toggleSchedulePanel()">⏱ <span id="scheduleLabel">定时</span> ▾</button>
            <div class="schedule-dropdown" id="scheduleDropdown" style="display:none;">
              <div class="schedule-dropdown-title">定时测活间隔</div>
              <label class="schedule-option"><input type="radio" name="scheduleInterval" value="0" onchange="setScheduleInterval(0)"> <span>关闭</span></label>
              <label class="schedule-option"><input type="radio" name="scheduleInterval" value="60" onchange="setScheduleInterval(60)"> <span>1 分钟</span></label>
              <label class="schedule-option"><input type="radio" name="scheduleInterval" value="300" onchange="setScheduleInterval(300)"> <span>5 分钟</span></label>
              <label class="schedule-option"><input type="radio" name="scheduleInterval" value="900" onchange="setScheduleInterval(900)"> <span>15 分钟</span></label>
              <label class="schedule-option"><input type="radio" name="scheduleInterval" value="1800" onchange="setScheduleInterval(1800)"> <span>30 分钟</span></label>
              <label class="schedule-option"><input type="radio" name="scheduleInterval" value="3600" onchange="setScheduleInterval(3600)"> <span>1 小时</span></label>
              <div class="schedule-divider"></div>
              <div class="schedule-row" style="display:flex; align-items:center; gap:6px; padding:4px 6px;">
                <label style="font-size:11.5px; color:var(--b-text); flex:1;">连续失败自动禁用</label>
                <input type="checkbox" id="autoDisableChk" checked onchange="setAutoDisable(this.checked)" style="accent-color:var(--b-accent); cursor:pointer;">
              </div>
              <div class="schedule-row" style="display:flex; align-items:center; gap:6px; padding:4px 6px;">
                <label style="font-size:11.5px; color:var(--b-text); flex:1;">失败次数阈值</label>
                <select id="thresholdSel" onchange="setDisableThreshold(parseInt(this.value,10))" style="background:var(--b-bg); color:var(--b-text); border:1px solid var(--b-line); border-radius:2px; padding:2px 5px; font-size:11px; outline:none; cursor:pointer;">
                  <option value="1">1 次</option>
                  <option value="2">2 次</option>
                  <option value="3" selected>3 次</option>
                  <option value="5">5 次</option>
                  <option value="10">10 次</option>
                </select>
              </div>
              <div class="schedule-status" id="scheduleStatus">定时测活已关闭</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 视图 1: 已配置模型列表 -->
      <div class="model-view-pane active" id="paneModels">
        <div class="model-add-bar" style="margin-bottom: 8px;">
          <input class="input" id="newModelId" placeholder="模型 ID (如: gpt-4o, deepseek-chat)" style="flex: 1.2;">
          <input class="input" id="newModelName" placeholder="显示别名 (可选)" style="flex: 1;">
          <button class="btn btn-primary edit-action" onclick="addModelManual()">➕ 添加模型</button>
        </div>

        <div class="models-tag-container" id="modelsContainer">
          <span style="color: var(--b-text-3); font-size: 12px; padding: 6px;">暂无模型，点击「自动拉取远程模型」或手动添加。别名可直接点击修改</span>
        </div>
      </div>

      <!-- 视图 2: 远程拉取结果预览 -->
      <div class="model-view-pane" id="paneFetch">
        <div class="fetch-preview-container">
          <div class="fetch-preview-header">
            <span class="title">📥 远程拉取结果 (勾选后点「添加选中」写入)</span>
            <div class="actions">
              <button class="btn btn-emerald edit-action" onclick="commitFetchedModels()">✅ 添加选中</button>
              <button class="btn btn-indigo edit-action" onclick="testAllFetched()">⚡ 全部测活</button>
              <button class="btn btn-ghost edit-action" onclick="toggleAllFetched(true)">☑ 全选</button>
              <button class="btn btn-ghost edit-action" onclick="toggleAllFetched(false)">☐ 全不选</button>
              <button class="btn btn-ghost edit-action" onclick="switchModelWorkTab('models')">✕ 返回列表</button>
            </div>
          </div>
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; gap: 6px; flex-shrink: 0;">
            <div class="fetch-summary" id="fetchSummary" style="flex: 1;"></div>
            <input class="search-input" id="previewSearch" style="width: 120px; flex-shrink: 0;" placeholder="🔍 过滤拉取模型..." oninput="renderFetchPreview()">
          </div>
          <div class="fetch-preview-list" id="fetchPreviewList"></div>
        </div>
      </div>

    </div>
  </div>
</div>

<footer>
  <div class="footer-left">
    <span id="statusMsg">● 就绪</span>
  </div>
  <div class="footer-right">
    <span id="pathDisplay">📁 正在加载配置文件...</span>
    <span><kbd>Ctrl+S</kbd> 保存配置</span>
  </div>
</footer>

<script>
let currentConfig = { providers: {} };
let selectedPid = null;
let configTargets = [];
let currentConfigPath = null;
let currentEditable = true;
let currentSchema = 'pi-providers';
let fetchedPreview = []; // Buffer of {id, name, selected, added}
const configDrafts = {}; // 内存草稿字典: path -> { config, selectedPid, isProviderEditing, editForm }

async function refreshTargets(keepPath = true) {
  setStatus('正在加载 Agent 配置文件...', '#F59E0B');
  const result = await window.pywebview.api.discover_configs();
  configTargets = result.targets || [];
  const previousPath = keepPath ? currentConfigPath : null;
  if (previousPath && configTargets.some(t => t.path === previousPath)) {
    currentConfigPath = previousPath;
  } else if (configTargets.length > 0) {
    currentConfigPath = configTargets[0].path;
  } else {
    currentConfigPath = result.defaultPath;
  }
  renderTargetTabs();
  await loadData(currentConfigPath);
  setStatus('已就绪', '#10B981');
}

function renderTargetTabs() {
  const container = document.getElementById('targetTabs');
  if (!container) return;
  container.innerHTML = '';

  configTargets.forEach(target => {
    const item = document.createElement('div');
    const isActive = target.path === currentConfigPath;
    item.className = 'target-tab-item' + (isActive ? ' active' : '');
    item.innerHTML = `
      <span class="tab-icon">📁</span>
      <span>${target.label}</span>
    `;
    item.onclick = () => switchTarget(target.path);
    container.appendChild(item);
  });
}

function saveCurrentStateToDraft() {
  if (!currentConfigPath) return;
  const currentPid = syncCurrentFormToMemory();
  configDrafts[currentConfigPath] = {
    config: JSON.parse(JSON.stringify(currentConfig || { providers: {} })),
    selectedPid: currentPid || selectedPid,
    isProviderEditing: isProviderEditing,
    editForm: {
      pId: document.getElementById('pId') ? document.getElementById('pId').value : '',
      pName: document.getElementById('pName') ? document.getElementById('pName').value : '',
      pBaseUrl: document.getElementById('pBaseUrl') ? document.getElementById('pBaseUrl').value : '',
      pApiKey: document.getElementById('pApiKey') ? document.getElementById('pApiKey').value : '',
      pApi: document.getElementById('pApi') ? document.getElementById('pApi').value : 'openai-completions',
    },
    editable: currentEditable,
    schema: currentSchema,
  };
}

async function switchTarget(path) {
  if (path === currentConfigPath) return;
  // 切换前先将当前配置的表单输入与模型改动暂存到内存草稿
  saveCurrentStateToDraft();
  
  currentConfigPath = path;
  renderTargetTabs();
  await loadData(currentConfigPath);
}

async function loadData(path = currentConfigPath) {
  fetchedPreview = []; // clear buffer when reloading data
  const fpContainer = document.getElementById('fetchPreviewContainer');
  if (fpContainer) fpContainer.style.display = 'none';

  // 优先恢复内存中的未保存草稿
  if (configDrafts[path]) {
    const draft = configDrafts[path];
    currentConfig = draft.config;
    currentConfigPath = path;
    currentEditable = draft.editable !== false;
    currentSchema = draft.schema || 'unknown';
    document.getElementById('pathDisplay').innerText = `📁 当前配置: ${path}`;
    updateEditState();
    renderSidebar();
    
    if (draft.selectedPid && currentConfig.providers[draft.selectedPid]) {
      selectProvider(draft.selectedPid);
    } else {
      const keys = Object.keys(currentConfig.providers);
      if (keys.length > 0) selectProvider(keys[0]);
      else newProvider(true);
    }
    
    // 恢复编辑状态与未暂存的表单内容
    if (draft.isProviderEditing && draft.editForm) {
      toggleProviderEditMode(true);
      if (document.getElementById('pId')) document.getElementById('pId').value = draft.editForm.pId || '';
      if (document.getElementById('pName')) document.getElementById('pName').value = draft.editForm.pName || '';
      if (document.getElementById('pBaseUrl')) document.getElementById('pBaseUrl').value = draft.editForm.pBaseUrl || '';
      if (document.getElementById('pApiKey')) document.getElementById('pApiKey').value = draft.editForm.pApiKey || '';
      if (document.getElementById('pApi')) document.getElementById('pApi').value = draft.editForm.pApi || 'openai-completions';
    }
    return;
  }

  // 没有草稿时，从后端读取原始配置文件
  const data = await window.pywebview.api.get_config(path);
  currentConfig = data.config;
  currentConfigPath = data.path;
  currentEditable = data.editable !== false;
  currentSchema = data.schema || 'unknown';
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

function toggleApiKeyVisibility() {
  const input = document.getElementById('pApiKey');
  const btn = document.getElementById('toggleApiKeyBtn');
  if (input.type === 'password') {
    input.type = 'text';
    btn.textContent = '🙈';
  } else {
    input.type = 'password';
    btn.textContent = '👁️';
  }
}

function getProtoBadge(api) {
  if (api === 'anthropic-messages') return '<span class="p-proto" style="background:rgba(217,70,239,0.18); color:#F0ABFC; border-color:rgba(217,70,239,0.3);">Claude</span>';
  if (api === 'google-generative-ai') return '<span class="p-proto" style="background:rgba(16,185,129,0.18); color:#6EE7B7; border-color:rgba(16,185,129,0.3);">Gemini</span>';
  if (api === 'openai-responses') return '<span class="p-proto" style="background:rgba(99,102,241,0.18); color:#A5B4FC; border-color:rgba(99,102,241,0.3);">Resp</span>';
  return '<span class="p-proto">OpenAI</span>';
}

function renderSidebar() {
  const container = document.getElementById('providerList');
  container.innerHTML = '';
  const searchInput = document.getElementById('providerSearch');
  const query = searchInput ? searchInput.value.trim().toLowerCase() : '';
  let pids = Object.keys(currentConfig.providers).sort();
  if (query) {
    pids = pids.filter(pid => {
      const p = currentConfig.providers[pid] || {};
      return pid.toLowerCase().includes(query) || (p.name && p.name.toLowerCase().includes(query));
    });
  }
  if (pids.length === 0) {
    container.innerHTML = `<div style="color:var(--text-dim); font-size:12px; text-align:center; padding:18px 0;">${query ? '未找到匹配服务商' : '暂无服务商配置'}</div>`;
    return;
  }
  pids.forEach(pid => {
    const p = currentConfig.providers[pid];
    const count = (p.models || []).length;
    const card = document.createElement('div');
    card.className = 'p-card' + (pid === selectedPid ? ' active' : '');
    card.onclick = () => selectProvider(pid);
    card.innerHTML = `
      <div class="p-card-top">
        <span class="p-name" title="${p.name || pid}">${p.name || pid}</span>
        <div class="p-badges">
          ${getProtoBadge(p.api)}
          <span class="p-count">${count}</span>
        </div>
      </div>
      <div class="p-id">${pid}</div>
    `;
    container.appendChild(card);
  });
}

let isProviderEditing = false;
let isViewKeyMasked = true;

function toggleViewKeyMask() {
  isViewKeyMasked = !isViewKeyMasked;
  const btn = document.getElementById('viewMaskBtn');
  if (btn) btn.textContent = isViewKeyMasked ? '👁️' : '🙈';
  if (selectedPid && currentConfig.providers[selectedPid]) {
    updateProviderViewPanel(selectedPid);
  }
}

function updateProviderViewPanel(pid) {
  const p = (pid && currentConfig.providers[pid]) ? currentConfig.providers[pid] : null;
  const vId = document.getElementById('vId');
  const vName = document.getElementById('vName');
  const vBaseUrl = document.getElementById('vBaseUrl');
  const vApiKey = document.getElementById('vApiKey');
  const vApi = document.getElementById('vApi');

  if (!p) {
    if (vId) vId.innerText = '-';
    if (vName) { vName.innerText = '未选择服务商'; vName.className = 'view-value empty'; }
    if (vBaseUrl) { vBaseUrl.innerText = '-'; vBaseUrl.className = 'view-value empty'; }
    if (vApiKey) { vApiKey.innerText = '-'; vApiKey.className = 'view-value empty'; }
    if (vApi) { vApi.innerText = '-'; vApi.className = 'view-value empty'; }
    return;
  }

  if (vId) { vId.innerText = pid; vId.className = 'view-value'; }
  if (vName) {
    vName.innerText = p.name || '（未设置别名）';
    vName.className = p.name ? 'view-value' : 'view-value empty';
  }
  if (vBaseUrl) {
    vBaseUrl.innerText = p.baseUrl || '（未配置 Base URL）';
    vBaseUrl.className = p.baseUrl ? 'view-value' : 'view-value empty';
  }
  if (vApiKey) {
    if (!p.apiKey) {
      vApiKey.innerText = '（无需或未填写 Key）';
      vApiKey.className = 'view-value empty';
    } else if (isViewKeyMasked) {
      const raw = p.apiKey;
      vApiKey.innerText = raw.length > 8 ? raw.slice(0, 4) + '••••••••' + raw.slice(-3) : '••••••••';
      vApiKey.className = 'view-value';
    } else {
      vApiKey.innerText = p.apiKey;
      vApiKey.className = 'view-value';
    }
  }
  if (vApi) {
    vApi.innerText = p.api || 'openai-completions';
    vApi.className = 'view-value';
  }
}

function toggleProviderEditMode(editing) {
  if (editing && !assertEditable()) return;
  isProviderEditing = editing;
  const viewPanel = document.getElementById('providerViewPanel');
  const editPanel = document.getElementById('providerEditPanel');
  const editBtn = document.getElementById('editProviderBtn');
  const saveBtn = document.getElementById('saveProviderBtn');
  const cancelBtn = document.getElementById('cancelProviderBtn');

  if (editing) {
    if (viewPanel) viewPanel.style.display = 'none';
    if (editPanel) editPanel.style.display = 'flex';
    if (editBtn) editBtn.style.display = 'none';
    if (saveBtn) saveBtn.style.display = 'inline-flex';
    if (cancelBtn) cancelBtn.style.display = 'inline-flex';
    document.getElementById('pId').focus();
  } else {
    if (viewPanel) viewPanel.style.display = 'flex';
    if (editPanel) editPanel.style.display = 'none';
    if (editBtn) editBtn.style.display = 'inline-flex';
    if (saveBtn) saveBtn.style.display = 'none';
    if (cancelBtn) cancelBtn.style.display = 'none';
    if (selectedPid) updateProviderViewPanel(selectedPid);
  }
}

async function saveProviderEdit() {
  if (!assertEditable()) return;
  const pIdInput = document.getElementById('pId');
  const rawId = pIdInput ? pIdInput.value : '';
  const pid = normalizeProviderId(rawId);
  if (!pid) return alert('服务商 ID 不能为空');
  
  // 如果是新建服务商且 ID 已存在
  if (!selectedPid && currentConfig.providers[pid]) {
    return alert(`服务商 ID [${pid}] 已存在，请使用其他 ID`);
  }

  selectedPid = pid;
  syncCurrentFormToMemory();
  const saved = await saveAll();
  if (!saved) return;
  toggleProviderEditMode(false);
  renderSidebar();
  updateProviderViewPanel(pid);
  setStatus(`✅ 已保存服务商 [${pid}]`, '#10B981');
}

function cancelProviderEdit() {
  if (selectedPid && currentConfig.providers[selectedPid]) {
    selectProvider(selectedPid);
  } else {
    const keys = Object.keys(currentConfig.providers);
    if (keys.length > 0) selectProvider(keys[0]);
    else toggleProviderEditMode(false);
  }
  toggleProviderEditMode(false);
}

function selectProvider(pid) {
  selectedPid = pid;
  if (window.pywebview && window.pywebview.api && window.pywebview.api.set_selected_provider) {
    window.pywebview.api.set_selected_provider(pid).catch(() => {});
  }
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
  
  updateProviderViewPanel(pid);
  toggleProviderEditMode(false);
  renderModels(p.models || []);
}

function switchModelWorkTab(tab) {
  const btnModels = document.getElementById('tabBtnModels');
  const btnFetch = document.getElementById('tabBtnFetch');
  const paneModels = document.getElementById('paneModels');
  const paneFetch = document.getElementById('paneFetch');
  
  if (tab === 'fetch') {
    if (btnModels) btnModels.classList.remove('active');
    if (btnFetch) btnFetch.classList.add('active');
    if (paneModels) paneModels.classList.remove('active');
    if (paneFetch) paneFetch.classList.add('active');
  } else {
    if (btnModels) btnModels.classList.add('active');
    if (btnFetch) btnFetch.classList.remove('active');
    if (paneModels) paneModels.classList.add('active');
    if (paneFetch) paneFetch.classList.remove('active');
  }
}

function renderModels(models) {
  const pid = selectedPid || syncCurrentFormToMemory();
  const p = (pid && currentConfig.providers[pid]) ? currentConfig.providers[pid] : {};
  const actualList = models !== undefined ? models : (p.models || []);
  
  // 更新模型总数 Badge
  const badge = document.getElementById('modelsCountBadge');
  if (badge) badge.innerText = `${actualList.length} models`;
  const tabBadge = document.getElementById('modelsTabBadge');
  if (tabBadge) tabBadge.innerText = `${actualList.length}`;

  const container = document.getElementById('modelsContainer');
  container.innerHTML = '';
  if (!actualList || actualList.length === 0) {
    container.innerHTML = '<span style="color: var(--text-muted); font-size: 13px;">暂无模型，点击「自动拉取模型」或手动添加。别名可直接点击修改</span>';
    return;
  }

  const searchInput = document.getElementById('modelSearch');
  const query = searchInput ? searchInput.value.trim().toLowerCase() : '';
  let displayList = actualList;
  if (query) {
    displayList = displayList.filter(m => {
      const id = String(m.id || '').toLowerCase();
      const name = String(m.name || '').toLowerCase();
      return id.includes(query) || name.includes(query);
    });
  }

  if (displayList.length === 0) {
    container.innerHTML = `<span style="color: var(--text-muted); font-size: 12px; padding: 6px 0;">未搜索到包含 "${query}" 的模型</span>`;
    return;
  }

  displayList.forEach(m => {
    const tag = document.createElement('div');
    const isDisabled = !!m.disabled;
    const failStreak = m._failStreak || 0;
    tag.className = 'model-tag' + (isDisabled ? ' disabled' : '');
    const alias = m.name || m.id;
    const safeId = String(m.id).replace(/'/g, "\\'").replace(/"/g, '&quot;');
    const safeAlias = String(alias).replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const disabledBadge = isDisabled
      ? `<span class="disabled-badge" title="连续失败 ${failStreak} 次，已自动禁用。点击「启用」可恢复">⛔ 已禁用</span>`
      : (failStreak > 0 ? `<span class="fail-streak" title="连续失败 ${failStreak} 次 (达 ${disableThreshold} 次会自动禁用)">⚠ ${failStreak}</span>` : '');
    const toggleTitle = isDisabled ? '点击重新启用此模型' : '点击手动禁用此模型';
    const toggleIcon = isDisabled ? '🔓' : '🔒';
    tag.innerHTML = `
      <span class="alias-icon" title="可直接编辑此别名">✏️</span>
      <input class="alias-input" type="text" value="${safeAlias}" placeholder="${safeId}"
             title="点击直接修改别名，回车或失焦自动保存"
             onchange="updateModelAlias('${safeId}', this.value)">
      <span class="alias-id" title="${safeId}">${safeId}</span>
      ${disabledBadge}
      <span class="test-btn" onclick="testModel(this, '${safeId}')" title="测活：发送最小请求验证该模型 API 是否接通">⚡ 测活</span>
      <span class="toggle-btn ${isDisabled ? 'on' : 'off'}" onclick="toggleModelEnabled('${safeId}')" title="${toggleTitle}">${toggleIcon}</span>
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

function toggleModelEnabled(mid) {
  if (!assertEditable()) return;
  const pid = syncCurrentFormToMemory();
  if (!pid) return;
  const p = currentConfig.providers[pid];
  if (!p || !p.models) return;
  const m = p.models.find(x => x.id === mid);
  if (!m) return;
  if (m.disabled) {
    delete m.disabled;
    m._failStreak = 0;
    m._lastError = null;
    setStatus(`✅ [${mid}] 已重新启用`, '#10B981');
  } else {
    m.disabled = true;
    setStatus(`⏸ [${mid}] 已手动禁用 (点 💾 保存后生效)`, '#F59E0B');
  }
  renderModels(p.models);
}


function normalizeProviderId(raw) {
  return String(raw || '').trim().replace(/[^A-Za-z0-9_.-]+/g, '-');
}

function syncCurrentFormToMemory() {
  const pIdInput = document.getElementById('pId');
  if (!pIdInput) return selectedPid;
  const rawId = pIdInput.value;
  const pid = normalizeProviderId(rawId);
  if (!pid) return selectedPid || '';

  // 如果是在已有服务商上修改了 ID
  if (selectedPid && selectedPid !== pid) {
    if (currentConfig.providers[pid]) {
      alert('该服务商 ID 已存在');
      pIdInput.value = selectedPid;
      return selectedPid;
    }
    currentConfig.providers[pid] = currentConfig.providers[selectedPid] || { models: [] };
    delete currentConfig.providers[selectedPid];
    selectedPid = pid;
  } else if (!selectedPid) {
    // 新建服务商场景：selectedPid 为 null，将 pid 登记为选中服务商
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
  updateProviderViewPanel(null);
  toggleProviderEditMode(true);
  renderModels([]);
  const pIdInput = document.getElementById('pId');
  if (pIdInput) pIdInput.focus();
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
    switchModelWorkTab('fetch');
    setStatus(`成功拉取到 ${res.models.length} 个模型，请在预览区勾选后点击「添加选中」`, '#10B981');
  } catch (err) {
    alert('拉取模型失败: ' + err.message);
    setStatus('拉取模型失败: ' + err.message, '#EF4444');
  }
}

function renderFetchPreview() {
  const fetchBadge = document.getElementById('fetchTabBadge');
  const list = document.getElementById('fetchPreviewList');
  const summary = document.getElementById('fetchSummary');
  if (!fetchedPreview || fetchedPreview.length === 0) {
    if (fetchBadge) fetchBadge.style.display = 'none';
    if (list) list.innerHTML = '<div style="color:var(--b-text-3); font-size:12px; text-align:center; padding:20px 0;">暂无拉取结果</div>';
    return;
  }
  if (fetchBadge) {
    fetchBadge.style.display = 'inline-block';
    fetchBadge.innerText = String(fetchedPreview.length);
  }
  list.innerHTML = '';
  const selectedCount = fetchedPreview.filter(m => m.selected && !m.added).length;
  const addedCount = fetchedPreview.filter(m => m.added).length;
  summary.innerHTML = `共拉取 <b style="color:#fff;">${fetchedPreview.length}</b> 个 · 已选 <b style="color:var(--primary);">${selectedCount}</b> 个 · 已在列表中 <b style="color:var(--emerald);">${addedCount}</b> 个`;
  
  const searchInput = document.getElementById('previewSearch');
  const query = searchInput ? searchInput.value.trim().toLowerCase() : '';

  fetchedPreview.forEach((m, idx) => {
    if (query) {
      const id = String(m.id || '').toLowerCase();
      const name = String(m.name || '').toLowerCase();
      if (!id.includes(query) && !name.includes(query)) return;
    }
    const row = document.createElement('div');
    row.className = 'fetch-row' + (m.added ? ' added' : '');
    const safeId = String(m.id).replace(/'/g, "\\'").replace(/"/g, '&quot;');
    const safeName = String(m.name).replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    row.innerHTML = `
      <input type="checkbox" class="checkbox" ${m.selected ? 'checked' : ''} ${m.added ? 'disabled' : ''}
             onchange="fetchedPreview[${idx}].selected = this.checked; updateFetchSummary();">
      <span class="model-id" title="${safeId}">${safeId}</span>
      <input type="text" class="alias-input" value="${safeName}" placeholder="为该模型设置别名（可选）"
             onchange="fetchedPreview[${idx}].name = this.value.trim() || fetchedPreview[${idx}].id">
      <span class="test-btn" onclick="testModel(this, '${safeId}')" title="测活：验证该模型 API 是否接通">⚡</span>
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
  switchModelWorkTab('models');
  if (addedCount > 0) {
    setStatus(`✅ 已将 ${addedCount} 个模型添加到 [${pid}] 列表。点击「💾 保存」即可持久化`, '#10B981');
  } else {
    setStatus('没有选中可添加的模型，请先勾选', '#F59E0B');
  }
}

function currentTestContext() {
  return {
    baseUrl: document.getElementById('pBaseUrl').value.trim(),
    apiKey: document.getElementById('pApiKey').value.trim(),
    api: document.getElementById('pApi').value || 'openai-completions',
  };
}

async function testModel(btn, mid) {
  if (!assertEditable()) return;
  const ctx = currentTestContext();
  if (!ctx.baseUrl) return alert('请先填写 Base URL');
  btn.classList.add('testing');
  btn.classList.remove('ok', 'fail');
  btn.innerHTML = '⏳';
  btn.title = '正在检测...';
  try {
    const res = await window.pywebview.api.test_model(ctx.baseUrl, ctx.apiKey, ctx.api, mid);
    if (res.success) {
      btn.classList.add('ok');
      btn.innerHTML = '✓';
      btn.title = `可用 · ${res.latency_ms}ms`;
      setStatus(`✅ [${mid}] 测活成功 · ${res.latency_ms}ms`, '#10B981');
    } else {
      btn.classList.add('fail');
      btn.innerHTML = '✗';
      btn.title = `失败: ${res.error || '未知错误'}`;
      setStatus(`❌ [${mid}] 测活失败: ${res.error || '未知错误'}`, '#EF4444');
    }
  } catch (e) {
    btn.classList.add('fail');
    btn.innerHTML = '✗';
    btn.title = '检测异常';
    setStatus(`❌ [${mid}] 测活异常`, '#EF4444');
  }
  setTimeout(() => btn.classList.remove('testing'), 300);
}

async function testAllFetched() {
  if (!assertEditable()) return;
  if (!fetchedPreview || fetchedPreview.length === 0) return;
  const ctx = currentTestContext();
  if (!ctx.baseUrl) return alert('请先填写 Base URL');
  setStatus(`正在批量测活 ${fetchedPreview.length} 个模型...`, '#F59E0B');
  let okCount = 0, failCount = 0;
  for (let i = 0; i < fetchedPreview.length; i++) {
    const btn = document.querySelectorAll('#fetchPreviewList .test-btn')[i];
    if (!btn) continue;
    btn.classList.add('testing');
    btn.classList.remove('ok', 'fail');
    btn.innerHTML = '⏳';
    try {
      const res = await window.pywebview.api.test_model(ctx.baseUrl, ctx.apiKey, ctx.api, fetchedPreview[i].id);
      if (res.success) {
        btn.classList.add('ok');
        btn.innerHTML = '✓';
        btn.title = `可用 · ${res.latency_ms}ms`;
        okCount++;
      } else {
        btn.classList.add('fail');
        btn.innerHTML = '✗';
        btn.title = `失败: ${res.error || '未知错误'}`;
        failCount++;
      }
    } catch (e) {
      btn.classList.add('fail');
      btn.innerHTML = '✗';
      failCount++;
    }
    btn.classList.remove('testing');
  }
  setStatus(`批量测活完成：${okCount} 个可用，${failCount} 个失败`, failCount > 0 ? (okCount > 0 ? '#F59E0B' : '#EF4444') : '#10B981');
}

function closeFetchPreview() {
  fetchedPreview = [];
  const c = document.getElementById('fetchPreviewContainer');
  if (c) c.style.display = 'none';
}

// ============================================================
// 全部模型测活 + 定时测活 (Periodic Health Check)
// ============================================================
let testAllInProgress = false;
let testAllResults = { ok: 0, fail: 0, lastAt: null, disabled: 0, reenabled: 0 };
let scheduleIntervalSec = 0;
let scheduleTimer = null;
let scheduleCountdown = null;
let scheduleNextAt = 0;
let disableThreshold = 3;   // 连续失败 N 次自动禁用
let autoDisableEnabled = true;

function updateHealthSummary() {
  const wrap = document.getElementById('healthSummary');
  if (!wrap) return;
  const hasResult = testAllResults.lastAt !== null;
  wrap.style.display = (hasResult || testAllInProgress) ? 'inline-flex' : 'none';
  document.getElementById('healthOkCount').innerText = testAllResults.ok;
  document.getElementById('healthFailCount').innerText = testAllResults.fail;
  const meta = document.getElementById('healthMeta');
  if (testAllInProgress) {
    meta.innerText = '⏳ 测活中...';
    meta.classList.add('testing');
  } else if (testAllResults.lastAt) {
    const t = new Date(testAllResults.lastAt);
    const hh = String(t.getHours()).padStart(2, '0');
    const mm = String(t.getMinutes()).padStart(2, '0');
    const ss = String(t.getSeconds()).padStart(2, '0');
    meta.innerText = `上次 ${hh}:${mm}:${ss}`;
    meta.classList.remove('testing');
  }
}

async function testAllModels() {
  if (testAllInProgress) return;
  if (!currentEditable) { alert('当前配置是只读预览，无法测活。'); return; }
  const pid = syncCurrentFormToMemory();
  if (!pid) return alert('请先输入服务商 ID');
  const p = currentConfig.providers[pid];
  const models = (p && p.models) || [];
  if (models.length === 0) return alert('当前服务商还没有任何模型');
  const ctx = currentTestContext();
  if (!ctx.baseUrl) return alert('请先填写 Base URL');

  testAllInProgress = true;
  testAllResults = { ok: 0, fail: 0, lastAt: null, disabled: 0, reenabled: 0 };
  updateHealthSummary();
  setStatus(`⏳ 正在依次测活 ${models.length} 个模型...`, '#F59E0B');

  const tags = document.querySelectorAll('#modelsContainer .model-tag');
  tags.forEach(t => t.classList.add('testing-all'));

  const startTime = Date.now();
  for (let i = 0; i < models.length; i++) {
    const m = models[i];
    const tag = tags[i];
    const btn = tag ? tag.querySelector('.test-btn') : null;
    if (btn) { btn.classList.add('testing'); btn.classList.remove('ok', 'fail'); btn.innerHTML = '⏳'; }
    let res;
    try {
      res = await window.pywebview.api.test_model(ctx.baseUrl, ctx.apiKey, ctx.api, m.id);
    } catch (e) {
      res = { success: false, error: String(e) };
    }
    if (res.success) {
      if (btn) { btn.classList.add('ok'); btn.innerHTML = '✓'; btn.title = `可用 · ${res.latency_ms}ms`; }
      testAllResults.ok++;
      // 成功后清零连续失败计数并恢复启用
      if (m._failStreak && m._failStreak > 0) {
        if (m.disabled && autoDisableEnabled) {
          m.disabled = false;
          testAllResults.reenabled++;
        }
      }
      m._failStreak = 0;
      m._lastError = null;
    } else {
      if (btn) { btn.classList.add('fail'); btn.innerHTML = '✗'; btn.title = `失败: ${res.error || '未知错误'}`; }
      testAllResults.fail++;
      m._failStreak = (m._failStreak || 0) + 1;
      m._lastError = res.error || '未知错误';
      // 达到阈值后自动禁用
      if (autoDisableEnabled && !m.disabled && m._failStreak >= disableThreshold) {
        m.disabled = true;
        testAllResults.disabled++;
        if (btn) btn.title = `连续失败 ${m._failStreak} 次，已自动禁用 (${m._lastError})`;
      }
    }
    if (btn) btn.classList.remove('testing');
    updateHealthSummary();
  }
  tags.forEach(t => t.classList.remove('testing-all'));
  // 重新渲染以反映 disabled 状态变化
  renderModels(p.models);
  testAllInProgress = false;
  testAllResults.lastAt = Date.now();
  updateHealthSummary();
  const totalSec = ((Date.now() - startTime) / 1000).toFixed(1);
  const disabledText = testAllResults.disabled > 0 ? ` / ${testAllResults.disabled} 已被禁用` : '';
  const reText = testAllResults.reenabled > 0 ? ` / ${testAllResults.reenabled} 重新启用` : '';
  setStatus(`✅ 全部测活完成 (耗时 ${totalSec}s)：${testAllResults.ok} 可用 / ${testAllResults.fail} 失败${disabledText}${reText}`, testAllResults.fail > 0 ? '#F59E0B' : '#10B981');
}

function toggleSchedulePanel() {
  const dd = document.getElementById('scheduleDropdown');
  dd.style.display = (dd.style.display === 'none' || !dd.style.display) ? 'block' : 'none';
}

function setAutoDisable(enabled) {
  autoDisableEnabled = !!enabled;
  setStatus(autoDisableEnabled ? '已开启自动禁用不可用模型' : '已关闭自动禁用', autoDisableEnabled ? '#10B981' : '#F59E0B');
  if (autoDisableEnabled) {
    const status = document.getElementById('scheduleStatus');
    if (status && scheduleIntervalSec > 0) {
      status.innerText = `⏱ 失败 ${disableThreshold} 次后自动禁用 · ${Math.max(0, Math.round((scheduleNextAt - Date.now()) / 1000))}秒后轮询`;
    }
  }
}

function setDisableThreshold(n) {
  disableThreshold = Math.max(1, parseInt(n, 10) || 3);
  setStatus(`失败阈值已设为 ${disableThreshold} 次`, '#3B82F6');
  if (selectedPid) {
    const cur = currentConfig.providers[selectedPid];
    if (cur) renderModels(cur.models || []);
  }
}

function setScheduleInterval(sec) {
  scheduleIntervalSec = parseInt(sec, 10) || 0;
  if (scheduleTimer) { clearInterval(scheduleTimer); scheduleTimer = null; }
  if (scheduleCountdown) { clearInterval(scheduleCountdown); scheduleCountdown = null; }
  const btn = document.getElementById('scheduleBtn');
  const label = document.getElementById('scheduleLabel');
  const status = document.getElementById('scheduleStatus');
  if (scheduleIntervalSec <= 0) {
    btn.classList.remove('active');
    label.innerText = '定时';
    status.classList.remove('active');
    status.innerText = '定时测活已关闭';
    return;
  }
  btn.classList.add('active');
  const minute = scheduleIntervalSec >= 60 ? `${scheduleIntervalSec / 60}分钟` : `${scheduleIntervalSec}秒`;
  label.innerText = minute;
  scheduleNextAt = Date.now() + scheduleIntervalSec * 1000;
  status.classList.add('active');
  status.innerText = `⏱ 每${minute}自动测活所有模型`;
  scheduleTimer = setInterval(runScheduledTest, scheduleIntervalSec * 1000);
  scheduleCountdown = setInterval(updateScheduleStatus, 1000);
  updateScheduleStatus();
}

function updateScheduleStatus() {
  if (scheduleIntervalSec <= 0) return;
  const status = document.getElementById('scheduleStatus');
  if (testAllInProgress) {
    status.innerText = `🔄 正在执行定时测活...`;
    return;
  }
  const remain = Math.max(0, Math.round((scheduleNextAt - Date.now()) / 1000));
  const mm = Math.floor(remain / 60);
  const ss = remain % 60;
  const remainText = mm > 0 ? `${mm}分${ss}秒` : `${ss}秒`;
  status.innerText = `⏱ 下次自动测活：${remainText}后`;
}

async function runScheduledTest() {
  if (testAllInProgress) return;
  if (!currentEditable) return;
  const providers = currentConfig.providers || {};
  const allProviders = Object.keys(providers);
  if (allProviders.length === 0) return;
  let newlyDisabled = 0;
  let newlyReenabled = 0;
  let totalOk = 0, totalFail = 0;
  for (const pid of allProviders) {
    const p = providers[pid];
    const models = (p && p.models) || [];
    if (!p.baseUrl || models.length === 0) continue;
    for (const m of models) {
      let res;
      try {
        res = await window.pywebview.api.test_model(p.baseUrl, p.apiKey || '', p.api || 'openai-completions', m.id);
      } catch (e) {
        res = { success: false, error: String(e) };
      }
      if (res.success) {
        totalOk++;
        if (m._failStreak && m._failStreak > 0 && m.disabled && autoDisableEnabled) {
          m.disabled = false;
          newlyReenabled++;
        }
        m._failStreak = 0;
        m._lastError = null;
      } else {
        totalFail++;
        m._failStreak = (m._failStreak || 0) + 1;
        m._lastError = res.error || '未知错误';
        if (autoDisableEnabled && !m.disabled && m._failStreak >= disableThreshold) {
          m.disabled = true;
          newlyDisabled++;
        }
      }
    }
  }
  scheduleNextAt = Date.now() + scheduleIntervalSec * 1000;
  // 刷新当前显示
  if (selectedPid) {
    const cur = currentConfig.providers[selectedPid];
    if (cur) renderModels(cur.models || []);
  }
  const note = newlyDisabled > 0 || newlyReenabled > 0
    ? `（${newlyDisabled > 0 ? `禁用 ${newlyDisabled} 个, ` : ''}${newlyReenabled > 0 ? `恢复 ${newlyReenabled} 个` : ''}）`
    : '';
  setStatus(`⏱ 定时测活：${totalOk} 可用 / ${totalFail} 失败${note}`, '#3B82F6');
}

document.addEventListener('click', (e) => {
  const scheduleWrap = document.querySelector('.schedule-wrap');
  if (scheduleWrap && !scheduleWrap.contains(e.target)) {
    const dd = document.getElementById('scheduleDropdown');
    if (dd) dd.style.display = 'none';
  }
});


function deleteCurrentProvider() {
  if (!assertEditable()) return;
  if (!selectedPid) return;
  if (!confirm(`确定删除服务商 [${selectedPid}] 吗？`)) return;
  const deletedPid = selectedPid;
  delete currentConfig.providers[selectedPid];
  newProvider();
  saveAll();
  setStatus(`🗑️ 已删除服务商 [${deletedPid}]`, '#EF4444');
}

async function saveAll() {
  if (!assertEditable()) return false;
  const pid = syncCurrentFormToMemory();
  setStatus('正在保存全局配置 (Ctrl+S)...', '#F59E0B');
  const res = await window.pywebview.api.save_config(currentConfig, currentConfigPath);
  if (res.success) {
    // 写入成功后同步清除当前路径草稿
    delete configDrafts[currentConfigPath];
    const countText = `${res.providerCount || 0} providers / ${res.modelCount || 0} models`;
    setStatus(`✅ 已保存配置 (${countText}) · 快捷键 [Ctrl+S]`, '#10B981');
    renderSidebar();
    if (pid) {
      selectedPid = pid;
      updateProviderViewPanel(pid);
    }
    return true;
  } else {
    setStatus('❌ 保存失败: ' + res.error, '#EF4444');
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

async function exportCurrentProvider() {
  if (!selectedPid) {
    setStatus('请先在左侧选择一个服务商再导出', '#F59E0B');
    return;
  }
  syncCurrentFormToMemory();
  setStatus('正在导出当前服务商 TXT...', '#F59E0B');
  const res = await window.pywebview.api.export_provider_txt(currentConfig, currentConfigPath, selectedPid);
  if (res.success) {
    setStatus(`已导出当前 TXT：${res.path}`, '#10B981');
  } else {
    setStatus('导出失败: ' + res.error, '#EF4444');
  }
}

async function exportAllProviders() {
  syncCurrentFormToMemory();
  setStatus('正在导出全部服务商 TXT...', '#F59E0B');
  const res = await window.pywebview.api.export_all_providers_txt(currentConfig, currentConfigPath);
  if (res.success) {
    setStatus(`已导出全部 TXT：${res.path}`, '#10B981');
  } else {
    setStatus('导出失败: ' + res.error, '#EF4444');
  }
}

function setStatus(msg, color = '#10B981') {
  const el = document.getElementById('statusMsg');
  el.innerText = '● ' + msg;
  el.style.color = color;
}

window.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
    e.preventDefault();
    saveAll();
  }
});

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
        title="模型配置",
        html=HTML_CONTENT,
        js_api=api,
        width=1120,
        height=720,
        min_size=(980, 620),
        frameless=True,
        easy_drag=False,
        background_color="#0F172A"
    )
    api.set_window(window)
    webview.start()

if __name__ == "__main__":
    main()
