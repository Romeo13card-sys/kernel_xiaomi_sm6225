#!/usr/bin/env python3
import html
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Read environment variables
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TARGET_CHAT = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip()
STATUS = os.environ.get("BUILD_STATUS", "failure").strip().lower()
IMAGE_FILE = os.environ.get("BUILD_FILE", "").strip()
ZIP_FILE = os.environ.get("ANYKERNEL_ZIP", "").strip()
LOG_FILE = os.environ.get("DEBUG_REPORT_PATH", "").strip()
START_TIME = os.environ.get("BUILD_START", "").strip()

def sys_log(msg):
    print(f"[CI-Telegram] {msg}", flush=True)

def sys_err(msg):
    print(f"[CI-Telegram] ERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(1)

if not BOT_TOKEN or not TARGET_CHAT:
    sys_err("Missing mandatory TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID secrets!")

API_ENDPOINT = f"https://api.telegram.org/bot{BOT_TOKEN}"

def api_call(method, payload=None):
    data = urllib.parse.urlencode(payload or {}).encode("utf-8")
    req = urllib.request.Request(f"{API_ENDPOINT}/{method}", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if not res.get("ok"):
                sys_err(f"API call '{method}' failed: {res.get('description')}")
            return res.get("result")
    except Exception as err:
        sys_err(f"Network error on {method}: {err}")

def send_file(file_path, text_caption=""):
    path = Path(file_path)
    if not path.is_file():
        sys_log(f"File not found, skipping send: {path}")
        return

    sys_log(f"Uploading artifact: {path.name}...")
    boundary = "===CI_BUILD_BOUNDARY==="
    payload = bytearray()

    # Form parameters
    params = {
        "chat_id": TARGET_CHAT,
        "caption": text_caption[:1024],
        "parse_mode": "HTML"
    }

    for key, val in params.items():
        payload.extend(f"--{boundary}\r\n".encode())
        payload.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n{val}\r\n'.encode())

    # File attachment
    payload.extend(f"--{boundary}\r\n".encode())
    payload.extend(f'Content-Disposition: form-data; name="document"; filename="{path.name}"\r\n'.encode())
    payload.extend(b"Content-Type: application/octet-stream\r\n\r\n")
    
    with open(path, "rb") as f:
        payload.extend(f.read())
    payload.extend(f"\r\n--{boundary}--\r\n".encode())

    req = urllib.request.Request(
        f"{API_ENDPOINT}/sendDocument",
        data=bytes(payload),
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            sys_log(f"File successfully delivered: {path.name}")
    except Exception as err:
        sys_log(f"Failed to dispatch {path.name}: {err}")

def compose_status_report():
    time_str = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M:%S")
    repo = html.escape(os.environ.get("GITHUB_REPOSITORY", "Unknown Repo"))
    branch = html.escape(os.environ.get("GITHUB_REF_NAME", "main"))
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    
    is_success = STATUS in ("success", "successful", "ok")
    badge = "🟢 SUCCESS" if is_success else "🔴 FAILED"

    report = [
        f"<b>Kernel Pipeline Dispatcher</b>",
        f"<b>Status:</b> {badge}",
        f"<b>Timestamp:</b> <code>{time_str}</code>",
        "──────────────────",
        f"<b>Repository:</b> {repo}",
        f"<b>Target Branch:</b> <code>{branch}</code>"
    ]

    if run_id:
        report.append(f"<b>GitHub Run ID:</b> {run_id}")

    if not is_success and LOG_FILE:
        log_p = Path(LOG_FILE)
        if log_p.is_file():
            try:
                tail_content = html.escape(log_p.read_text(errors="ignore")[-800:])
                report.extend([
                    "──────────────────",
                    "<b>Execution Error Snapshot:</b>",
                    f"<code>{tail_content}</code>"
                ])
            except Exception:
                pass

    return "\n".join(report)

def main():
    sys_log("Initializing notification workflow...")
    
    # Send base text report
    message_body = compose_status_report()
    api_call("sendMessage", {
        "chat_id": TARGET_CHAT,
        "text": message_body,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true"
    })

    # Send build artifacts if compilation passed
    if STATUS in ("success", "successful", "ok"):
        if IMAGE_FILE:
            send_file(IMAGE_FILE, "⚙️ <b>Compiled Image Target</b>")
        if ZIP_FILE:
            send_file(ZIP_FILE, "📦 <b>AnyKernel3 Installer Package</b>")

if __name__ == "__main__":
    main()
