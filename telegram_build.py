#!/usr/bin/env python3
import hashlib
import html
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHANNEL_ID_RAW = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip()
BUILD_START = os.environ.get("BUILD_START", "").strip()
BUILD_STATUS = os.environ.get("BUILD_STATUS", "failure").strip().lower()
BUILD_FILE = os.environ.get("BUILD_FILE", "").strip()
ANYKERNEL_ZIP = os.environ.get("ANYKERNEL_ZIP", "").strip()
DEBUG_REPORT_PATH = os.environ.get("DEBUG_REPORT_PATH", "").strip()

TIMEZONE = ZoneInfo("America/Sao_Paulo")


def log(message):
    print(f"[telegram-build] {message}", flush=True)


def die(message):
    print(f"[telegram-build] ERRO: {message}", file=sys.stderr, flush=True)
    raise SystemExit(1)


def shell(command, default=""):
    try:
        result = subprocess.run(
            command,
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return default


def first(*values):
    for value in values:
        if value is not None:
            value = str(value).strip()
            if value:
                return value
    return ""


def esc(value):
    return html.escape(str(value), quote=False)


if not BOT_TOKEN:
    die("TELEGRAM_BOT_TOKEN não foi recebido dos Repository Secrets.")

if not CHANNEL_ID_RAW:
    die("TELEGRAM_CHANNEL_ID não foi recebido dos Repository Secrets.")

try:
    CHANNEL_ID = int(CHANNEL_ID_RAW)
except ValueError:
    die("TELEGRAM_CHANNEL_ID precisa ser um número inteiro.")

# Убрана принудительная проверка "if CHANNEL_ID >= 0", чтобы разрешить личные сообщения по положительному ID

if ":" not in BOT_TOKEN:
    die("TELEGRAM_BOT_TOKEN tem formato inválido.")

API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def telegram_form(method, data=None, timeout=60):
    body = urllib.parse.urlencode(data or {}).encode("utf-8")
    request = urllib.request.Request(
        f"{API_BASE}/{method}",
        data=body,
        method="POST",
    )

    log(f"Telegram API -> {method}")

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        die(f"{method}: HTTP {exc.code}: {raw[:1200]}")
    except Exception as exc:
        die(f"{method}: falha de conexão: {exc}")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        die(f"{method}: Telegram retornou JSON inválido.")

    if not payload.get("ok"):
        die(f"{method}: {payload.get('description', 'erro desconhecido')}")

    return payload["result"]


def telegram_document(path, caption, timeout=600):
    path = Path(path)

    if not path.is_file():
        die(f"Arquivo para envio não existe: {path}")

    boundary = f"----TelegramBuild{uuid.uuid4().hex}"
    body = bytearray()

    fields = {
        "chat_id": str(CHANNEL_ID),
        "caption": caption[:1024],
        "parse_mode": "HTML",
    }

    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        )
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")

    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        (
            f'Content-Disposition: form-data; name="document"; '
            f'filename="{path.name}"\r\n'
        ).encode("utf-8")
    )
    body.extend(b"Content-Type: application/octet-stream\r\n\r\n")

    with path.open("rb") as file_handle:
        while True:
            chunk = file_handle.read(1024 * 1024)
            if not chunk:
                break
            body.extend(chunk)

    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())

    request = urllib.request.Request(
        f"{API_BASE}/sendDocument",
        data=bytes(body),
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    log(f"Telegram API -> sendDocument ({path.name})")

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        die(f"sendDocument: HTTP {exc.code}: {raw[:1200]}")
    except Exception as exc:
        die(f"sendDocument: falha de conexão: {exc}")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        die("sendDocument: Telegram retornou JSON inválido.")

    if not payload.get("ok"):
        die(f"sendDocument: {payload.get('description', 'erro desconhecido')}")

    return payload["result"]


def sha1_file(path):
    digest = hashlib.sha1()
    with open(path, "rb") as file_handle:
        while True:
            chunk = file_handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def human_size(size):
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.2f} {unit}"
        value /= 1024
    return str(size)


def kernel_version():
    version = shell(r"""awk -F' = ' '/^VERSION =/{print $2; exit}' Makefile""")
    patchlevel = shell(r"""awk -F' = ' '/^PATCHLEVEL =/{print $2; exit}' Makefile""")
    sublevel = shell(r"""awk -F' = ' '/^SUBLEVEL =/{print $2; exit}' Makefile""")
    extraversion = shell(r"""awk -F' = ' '/^EXTRAVERSION =/{print $2; exit}' Makefile""")

    if not version or not patchlevel:
        return ""

    result = f"{version}.{patchlevel}"
    if sublevel:
        result += f".{sublevel}"
    if extraversion:
        result += extraversion
    return result


def build_duration():
    if not BUILD_START:
        return ""

    try:
        start = int(float(BUILD_START))
    except ValueError:
        return ""

    elapsed = max(0, int(time.time()) - start)
    hours, rest = divmod(elapsed, 3600)
    minutes, seconds = divmod(rest, 60)

    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    return f"{minutes}m {seconds}s"


def detect_device():
    return first(
        os.environ.get("DEVICE"),
        os.environ.get("TARGET_DEVICE"),
        os.environ.get("PRODUCT_DEVICE"),
        os.environ.get("CODENAME"),
        os.environ.get("TARGET_PRODUCT"),
    )


def read_debug_excerpt():
    if not DEBUG_REPORT_PATH:
        return ""

    path = Path(DEBUG_REPORT_PATH)
    if not path.is_file():
        return ""

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""

    return text[-1400:]


def build_message(artifact):
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    project = repository.split("/")[-1] if repository else ""

    branch = first(
        os.environ.get("GITHUB_HEAD_REF"),
        os.environ.get("GITHUB_REF_NAME"),
        shell("git branch --show-current"),
    )

    full_commit = first(
        os.environ.get("GITHUB_SHA"),
        shell("git rev-parse HEAD"),
    )
    short_commit = full_commit[:12] if full_commit else ""
    commit_message = shell("git log -1 --pretty=%B")[:700]
    commit_author = shell("git log -1 --pretty=%an")

    actor = os.environ.get("GITHUB_ACTOR", "").strip()
    workflow = os.environ.get("GITHUB_WORKFLOW", "").strip()
    run_number = os.environ.get("GITHUB_RUN_NUMBER", "").strip()
    run_id = os.environ.get("GITHUB_RUN_ID", "").strip()

    compiler = shell("clang --version | head -n 1")
    linux_version = kernel_version()
    duration = build_duration()
    device = detect_device()

    date_text = datetime.now(TIMEZONE).strftime("%d/%m/%Y %H:%M:%S")

    if BUILD_STATUS in ("success", "successful", "ok"):
        icon = "✅"
        status_text = "BUILD SUCCESSFUL"
    elif BUILD_STATUS in ("cancelled", "canceled"):
        icon = "⚠️"
        status_text = "BUILD CANCELLED"
    else:
        icon = "❌"
        status_text = "BUILD FAILED"

    lines = [
        "<b>Build Update</b>",
        "",
        "<code>================================</code>",
        "",
        f"• <b>DATE:</b> {esc(date_text)}",
    ]

    if project:
        lines.append(f"• <b>PROJECT:</b> {esc(project)}")
    if device:
        lines.append(f"• <b>DEVICE:</b> {esc(device)}")
    if linux_version:
        lines.append(f"• <b>LINUX VERSION:</b> {esc(linux_version)}")
    if branch:
        lines.append(f"• <b>BRANCH:</b> <code>{esc(branch)}</code>")
    if compiler:
        lines.append(f"• <b>COMPILER:</b> {esc(compiler)}")

    if commit_message:
        lines.extend([
            "",
            "• <b>LAST COMMIT:</b>",
            f"<code>{esc(commit_message)}</code>",
        ])

    lines.extend([
        "",
        "<code>================================</code>",
        "",
        f"{icon} <b>{status_text}</b>",
    ])

    if repository:
        lines.append(f"• <b>REPOSITORY:</b> {esc(repository)}")
    if workflow:
        lines.append(f"• <b>WORKFLOW:</b> {esc(workflow)}")
    if run_number:
        lines.append(f"• <b>BUILD:</b> #{esc(run_number)}")
    if run_id:
        lines.append(f"• <b>RUN ID:</b> <code>{esc(run_id)}</code>")
    if actor:
        lines.append(f"• <b>ACTOR:</b> {esc(actor)}")
    if commit_author:
        lines.append(f"• <b>COMMIT AUTHOR:</b> {esc(commit_author)}")
    if short_commit:
        lines.append(f"• <b>COMMIT:</b> <code>{esc(short_commit)}</code>")
    if duration:
        lines.append(f"• <b>BUILD TIME:</b> {esc(duration)}")

    if artifact and artifact.is_file():
        digest = sha1_file(artifact)
        size = human_size(artifact.stat().st_size)
        lines.extend([
            "",
            "📦 <b>ARTIFACT</b>",
            f"• <b>FILE:</b> <code>{esc(artifact.name)}</code>",
            f"• <b>SIZE:</b> {esc(size)}",
            f"• <b>SHA1:</b> <code>{digest}</code>",
        ])
    else:
        lines.extend(["", "📦 <b>ARTIFACT:</b> não encontrado"])

    if BUILD_STATUS not in ("success", "successful", "ok"):
        excerpt = read_debug_excerpt()
        if excerpt:
            lines.extend([
                "",
                "🐞 <b>DEBUG — FINAL DO LOG:</b>",
                f"<code>{esc(excerpt)}</code>",
            ])

    return "\n".join(lines)


def main():
    log("Verificando token e canal...")

    me = telegram_form("getMe")
    log(f"Bot autenticado: @{me.get('username', '')}")

    chat = telegram_form("getChat", {"chat_id": str(CHANNEL_ID)})
    log(
        f"Destino encontrado: "
        f"{chat.get('title', chat.get('first_name', chat.get('id')))} ({chat.get('id')})"
    )

    artifact = None
    if BUILD_FILE:
        candidate = Path(BUILD_FILE)
        if candidate.is_file():
            artifact = candidate
            log(f"Image encontrada: {artifact}")
        else:
            log(f"BUILD_FILE informado mas não existe: {candidate}")
    else:
        log("BUILD_FILE não foi definido.")

    message = build_message(artifact)

    if len(message) > 4096:
        message = message[:4050] + "\n\n... truncado"

    sent = telegram_form(
        "sendMessage",
        {
            "chat_id": str(CHANNEL_ID),
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        },
    )
    log(f"Mensagem enviada. message_id={sent.get('message_id')}")

    if artifact and BUILD_STATUS in ("success", "successful", "ok"):
        digest = sha1_file(artifact)
        size = human_size(artifact.stat().st_size)
        caption = (
            f"📦 <b>{esc(artifact.name)}</b>\n"
            f"💾 {esc(size)}\n\n"
            f"🔐 <b>SHA1:</b>\n<code>{digest}</code>"
        )
        uploaded = telegram_document(artifact, caption)
        log(f"Arquivo enviado. message_id={uploaded.get('message_id')}")

    # Envia o AnyKernel3 zip também
    if ANYKERNEL_ZIP and BUILD_STATUS in ("success", "successful", "ok"):
        zip_path = Path(ANYKERNEL_ZIP)
        if zip_path.is_file():
            digest = sha1_file(zip_path)
            size = human_size(zip_path.stat().st_size)
            caption = (
                f"📦 <b>{esc(zip_path.name)}</b>\n"
                f"💾 {esc(size)}\n\n"
                f"🔐 <b>SHA1:</b>\n<code>{digest}</code>"
            )
            uploaded = telegram_document(zip_path, caption)
            log(f"AnyKernel3 zip enviado. message_id={uploaded.get('message_id')}")
        else:
            log(f"ANYKERNEL_ZIP informado mas não existe: {zip_path}")


if __name__ == "__main__":
    main()
