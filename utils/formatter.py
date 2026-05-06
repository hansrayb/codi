"""Telegram-safe formatting helpers for execution results."""

from __future__ import annotations

from html import escape
import re

from telegram.constants import ParseMode

from core.desktop_screenshot import ActiveWindowInfo, DesktopScreenshot
from core.edit_approval import PendingApproval
from core.env_config import EnvConfigUpdateResult
from core.local_shell import LocalShellResult
from core.self_maintenance import SelfCheckResult
from core.system_activity import ProcessGroupSummary, SystemActivityReport, SystemActivityRequest
from models.result import MessagePayload


def format_execution_payload(
    *,
    assistant_name: str,
    role: str,
    session_id: str,
    exit_code: int,
    stdout: str,
    stderr: str,
    max_output_length: int,
) -> MessagePayload:
    """Format a successful or failed execution response for Telegram."""

    primary_output = stdout.strip() if exit_code == 0 else (stderr.strip() or stdout.strip())
    primary_output = _normalize_output(primary_output)

    if exit_code != 0 and not primary_output:
        primary_output = "Task gagal tanpa detail error tambahan."

    if exit_code == 0 and not primary_output:
        return MessagePayload(
            text=(
                f"<b>{escape(_build_status_line(assistant_name, role, exit_code))}</b>\n\n"
                "Tidak ada output."
            ),
            parse_mode=ParseMode.HTML,
        )

    if len(primary_output) > max_output_length:
        attachment_text = _build_attachment_text(
            assistant_name=assistant_name,
            role=role,
            session_id=session_id,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
        )
        status_line = _build_status_line(assistant_name, role, exit_code)
        preview = _build_preview_text(primary_output)
        return MessagePayload(
            text=(
                f"<b>{escape(status_line)}</b>\n\n"
                f"{escape(preview)}\n\n"
                "Versi lengkap saya kirim sebagai file."
            ),
            parse_mode=ParseMode.HTML,
            attachment_filename=f"{session_id}-{role}-output.txt",
            attachment_bytes=attachment_text.encode("utf-8"),
        )

    if exit_code != 0:
        status_line = _build_status_line(assistant_name, role, exit_code)
        return MessagePayload(
            text=(
                f"<b>{escape(status_line)}</b>\n\n"
                f"{escape(primary_output)}"
            ),
            parse_mode=ParseMode.HTML,
        )
    return MessagePayload(
        text=escape(primary_output),
        parse_mode=ParseMode.HTML,
    )


def format_error_payload(message: str, *, assistant_name: str = "Codi") -> MessagePayload:
    """Return a simple HTML-safe error payload."""

    return MessagePayload(
        text=f"<b>{escape(assistant_name)} belum sempat menyelesaikan task ini.</b>\n\n{escape(message)}",
        parse_mode=ParseMode.HTML,
    )


def format_env_config_update_payload(
    *,
    assistant_name: str,
    result: EnvConfigUpdateResult,
) -> MessagePayload:
    """Return a Telegram-safe summary for a successful `.env` config update."""

    lines = [
        f"<b>{escape(assistant_name)} sudah merapikan konfigurasi lokal ini.</b>",
        "",
        f"Pengaturan: <code>{escape(result.key)}</code>",
        f"File: <code>{escape(str(result.env_path))}</code>",
        (
            f"Nilai sebelumnya: <code>{escape(result.old_value)}</code>"
            if result.old_value is not None
            else "Nilai sebelumnya: belum ada di file"
        ),
        f"Nilai sekarang: <code>{escape(result.new_value)}</code>",
    ]
    if result.changed and result.restart_required:
        lines.extend(
            [
                "",
                "Supaya perubahan ini langsung kepakai, saya akan restart sebentar lagi setelah pesan ini terkirim.",
            ]
        )
    elif result.changed:
        lines.extend(["", "Perubahannya sudah tersimpan di file lokal."])
    else:
        lines.extend(["", "Nilainya memang sudah sama, jadi saya tidak mengubah file."])

    return MessagePayload(
        text="\n".join(lines),
        parse_mode=ParseMode.HTML,
        post_send_action="restart_self" if result.changed and result.restart_required else None,
    )


def format_edit_approval_payload(
    *,
    assistant_name: str,
    pending: PendingApproval,
    post_approval_note: str | None = None,
) -> MessagePayload:
    """Return a Telegram message asking the user to approve prepared edits."""

    change_counts = {"added": 0, "modified": 0, "deleted": 0}
    for change in pending.changes:
        change_counts[change.change_type] = change_counts.get(change.change_type, 0) + 1

    preview_lines = []
    markers = {"added": "+", "modified": "~", "deleted": "-"}
    for change in pending.changes[:6]:
        marker = markers.get(change.change_type, "*")
        preview_lines.append(f"{marker} {change.relative_path}")
    if len(pending.changes) > 6:
        preview_lines.append(f"... dan {len(pending.changes) - 6} file lain")

    text_parts = [
        f"<b>{escape(assistant_name)} sudah menyiapkan perubahan untuk ditinjau.</b>",
        "",
        f"Repo: <code>{escape(str(pending.repo_root))}</code>",
        f"Approval ID: <code>{escape(pending.approval_id)}</code>",
        (
            "Perubahan: "
            f"{len(pending.changes)} file "
            f"(+{change_counts.get('added', 0)}, "
            f"~{change_counts.get('modified', 0)}, "
            f"-{change_counts.get('deleted', 0)})"
        ),
    ]
    if pending.summary_text:
        text_parts.extend(
            [
                "",
                f"Ringkasan: {escape(pending.summary_text)}",
            ]
        )
    if preview_lines:
        text_parts.extend(
            [
                "",
                "Preview file:",
                escape("\n".join(preview_lines)),
            ]
        )
    if post_approval_note:
        text_parts.extend(
            [
                "",
                "<b>Setelah approval:</b>",
                escape(post_approval_note),
            ]
        )
    diff_text = pending.diff_text or "(Tidak ada diff tekstual. Perubahan mungkin file biner atau metadata.)"
    return MessagePayload(
        text="\n".join(text_parts),
        parse_mode=ParseMode.HTML,
        attachment_filename=f"{pending.approval_id}-proposal.patch",
        attachment_bytes=diff_text.encode("utf-8"),
        inline_buttons=(
            ("✅ Lanjutkan", "edit:approve"),
            ("❌ Batal", "edit:reject"),
        ),
    )


def format_edit_approval_result(
    *,
    assistant_name: str,
    approved: bool,
    pending: PendingApproval,
) -> MessagePayload:
    """Return a Telegram payload for approve/reject outcomes."""

    if approved:
        message = (
            f"<b>{escape(assistant_name)} sudah meng-apply perubahan.</b>\n\n"
            f"Repo: <code>{escape(str(pending.repo_root))}</code>\n"
            f"Total file: {len(pending.changes)}\n"
            "Draft editnya tetap saya simpan, jadi kamu bisa lanjut revisi berikutnya tanpa mulai dari nol."
        )
    else:
        message = (
            f"<b>{escape(assistant_name)} membuang revisi terakhir dari draft ini.</b>\n\n"
            f"Repo: <code>{escape(str(pending.repo_root))}</code>\n"
            "Workspace edit saya kembalikan ke kondisi repo saat ini."
        )
    return MessagePayload(text=message, parse_mode=ParseMode.HTML)


def format_self_update_result(
    *,
    assistant_name: str,
    pending: PendingApproval,
    check_result: SelfCheckResult,
    max_output_length: int,
    restart_scheduled: bool,
) -> MessagePayload:
    """Return the apply result for Codi's own repo, including verification status."""

    lines = [
        f"<b>{escape(assistant_name)} sudah meng-apply perubahan ke dirinya sendiri.</b>",
        "",
        f"Repo: <code>{escape(str(pending.repo_root))}</code>",
        f"Total file: {len(pending.changes)}",
        (
            "Verifikasi compile: berhasil"
            if check_result.compile_ok
            else "Verifikasi compile: gagal"
        ),
        (
            "Verifikasi test: berhasil"
            if check_result.tests_ok
            else "Verifikasi test: gagal"
        ),
    ]
    if restart_scheduled:
        lines.extend(
            [
                "",
                "Semua pengecekan lolos. Saya akan restart sebentar lagi agar perubahan ini aktif.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "Perubahan sudah terpasang, tapi saya belum restart otomatis karena pengecekan belum semuanya lolos.",
            ]
        )

    detail_text = _build_self_update_detail_text(check_result)
    if len(detail_text) > max_output_length:
        return MessagePayload(
            text="\n".join(lines + ["", "Ringkasan detail saya kirim sebagai file."]),
            parse_mode=ParseMode.HTML,
            attachment_filename=f"{pending.approval_id}-self-check.txt",
            attachment_bytes=detail_text.encode("utf-8"),
            post_send_action="restart_self" if restart_scheduled else None,
        )

    lines.extend(
        [
            "",
            "<b>Ringkasan verifikasi:</b>",
            f"<pre>{escape(detail_text)}</pre>",
        ]
    )
    return MessagePayload(
        text="\n".join(lines),
        parse_mode=ParseMode.HTML,
        post_send_action="restart_self" if restart_scheduled else None,
    )


def format_system_activity_payload(
    *,
    assistant_name: str,
    request: SystemActivityRequest,
    report: SystemActivityReport,
    max_output_length: int,
) -> MessagePayload:
    """Return a Telegram-safe summary of local host activity."""

    title = _build_system_activity_title(assistant_name, request)
    body = _build_system_activity_text(request, report)
    if len(body) > max_output_length:
        preview = _build_preview_text(body, max_lines=18, max_chars=1100)
        return MessagePayload(
            text=(
                f"<b>{escape(title)}</b>\n\n"
                f"{escape(preview)}\n\n"
                "Versi lengkap saya kirim sebagai file."
            ),
            parse_mode=ParseMode.HTML,
            attachment_filename="system-activity.txt",
            attachment_bytes=body.encode("utf-8"),
        )

    return MessagePayload(
        text=f"<b>{escape(title)}</b>\n\n{escape(body)}",
        parse_mode=ParseMode.HTML,
    )


def format_desktop_screenshot_payload(
    *,
    assistant_name: str,
    screenshot: DesktopScreenshot,
    report: SystemActivityReport | None = None,
    include_summary_requested: bool = False,
) -> MessagePayload:
    """Return a Telegram payload containing a fresh desktop screenshot."""

    timestamp = screenshot.captured_at.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    mode_text = _describe_screenshot_mode(screenshot.mode)
    lines = [
        f"<b>{escape(assistant_name)} sudah ambil {escape(mode_text)}.</b>",
    ]

    summary_lines = _build_desktop_scene_summary_lines(screenshot, report)
    if summary_lines or include_summary_requested:
        lines.append("")
        lines.append("<b>Ringkasan isi layar:</b>")
        if summary_lines:
            lines.extend(summary_lines)
        else:
            lines.append(
                "Saya sudah kirim screenshot-nya, tapi ringkasan isi layar belum kebaca jelas dari sesi desktop ini."
            )

    lines.extend(
        [
            "",
            f"Waktu ambil: {escape(timestamp)}",
            f"Tool: {escape(screenshot.source)}",
        ]
    )

    return MessagePayload(
        text="\n".join(lines),
        parse_mode=ParseMode.HTML,
        photo_filename=screenshot.filename,
        photo_bytes=screenshot.image_bytes,
    )


def format_local_shell_payload(
    *,
    assistant_name: str,
    result: LocalShellResult,
    max_output_length: int,
) -> MessagePayload:
    """Return a Telegram-safe summary of a local shell command result."""

    title = f"{assistant_name} sudah menjalankan perintah shell lokal."
    detail_text = _build_local_shell_detail_text(result)
    preview_text = _normalize_output(result.stderr.strip() or result.stdout.strip())

    lines = [
        f"<b>{escape(title)}</b>",
        "",
        f"Shell: <code>{escape(result.shell_path)}</code>",
        f"Folder kerja: <code>{escape(str(result.cwd))}</code>",
        f"Exit code: <code>{result.exit_code}</code>",
        f"Command: <code>{escape(result.command)}</code>",
    ]
    if result.timed_out:
        lines.extend(
            [
                "",
                "Perintah ini kena timeout, jadi saya hentikan setelah menunggu terlalu lama.",
            ]
        )

    if not preview_text:
        return MessagePayload(
            text="\n".join(lines + ["", "Tidak ada output."]),
            parse_mode=ParseMode.HTML,
        )

    if len(preview_text) > max_output_length:
        preview = _build_preview_text(preview_text, max_lines=18, max_chars=1100)
        return MessagePayload(
            text="\n".join(
                lines
                + [
                    "",
                    f"<pre>{escape(preview)}</pre>",
                    "",
                    "Versi lengkap saya kirim sebagai file.",
                ]
            ),
            parse_mode=ParseMode.HTML,
            attachment_filename=f"shell-{result.shell}-output.txt",
            attachment_bytes=detail_text.encode("utf-8"),
        )

    return MessagePayload(
        text="\n".join(lines + ["", f"<pre>{escape(preview_text)}</pre>"]),
        parse_mode=ParseMode.HTML,
    )


def _build_attachment_text(
    *,
    assistant_name: str,
    role: str,
    session_id: str,
    exit_code: int,
    stdout: str,
    stderr: str,
) -> str:
    parts = [
        f"assistant={assistant_name}",
        f"role={role}",
        f"session={session_id}",
        f"exit_code={exit_code}",
        "",
        "[stdout]",
        stdout.strip() or "(empty)",
        "",
        "[stderr]",
        stderr.strip() or "(empty)",
    ]
    return "\n".join(parts)


def _build_local_shell_detail_text(result: LocalShellResult) -> str:
    parts = [
        f"shell={result.shell_path}",
        f"cwd={result.cwd}",
        f"exit_code={result.exit_code}",
        f"timed_out={str(result.timed_out).lower()}",
        f"command={result.command}",
        "",
        "[stdout]",
        result.stdout.strip() or "(empty)",
        "",
        "[stderr]",
        result.stderr.strip() or "(empty)",
    ]
    return "\n".join(parts)


def _build_self_update_detail_text(check_result: SelfCheckResult) -> str:
    parts = [
        "[compileall]",
        check_result.compile_output.strip() or "(empty)",
        "",
        "[tests]",
        check_result.test_output.strip() or "(empty)",
    ]
    return "\n".join(parts)


def _describe_screenshot_mode(mode: str) -> str:
    mapping = {
        "fullscreen": "screenshot layar penuh laptop ini",
        "current_monitor": "screenshot monitor aktif",
        "active_window": "screenshot jendela aktif",
    }
    return mapping.get(mode, "screenshot desktop saat ini")


def _build_desktop_scene_summary_lines(
    screenshot: DesktopScreenshot,
    report: SystemActivityReport | None,
) -> list[str]:
    lines: list[str] = []
    active_window = screenshot.active_window

    if active_window is not None:
        app_name = _humanize_window_app_name(active_window)
        if active_window.caption and app_name:
            lines.append(
                escape(
                    f'- Jendela yang paling depan terlihat {app_name} dengan judul "{active_window.caption}".'
                )
            )
        elif active_window.caption:
            lines.append(escape(f'- Jendela yang paling depan berjudul "{active_window.caption}".'))
        elif app_name:
            lines.append(escape(f"- Jendela yang paling depan tampaknya berasal dari {app_name}."))

        if active_window.active_output_name:
            lines.append(escape(f"- Monitor aktif yang terdeteksi: {active_window.active_output_name}."))

    if report is not None and report.desktop_apps:
        top_labels = [group.label for group in report.desktop_apps[:3]]
        label_text = _join_labels_naturally(top_labels)
        if len(report.desktop_apps) > len(top_labels):
            remaining_count = len(report.desktop_apps) - len(top_labels)
            lines.append(
                escape(
                    f"- Aplikasi yang paling kelihatan saat ini antara lain {label_text}, plus {remaining_count} aplikasi lain."
                )
            )
        else:
            lines.append(escape(f"- Aplikasi yang paling kelihatan saat ini antara lain {label_text}."))

    return lines


def _humanize_window_app_name(active_window: ActiveWindowInfo) -> str | None:
    for value in (active_window.app_id, active_window.resource_class):
        if not value:
            continue
        candidate = value.split("/")[-1].split(".")[-1].replace("_", " ").replace("-", " ").strip()
        if candidate:
            return " ".join(word.capitalize() for word in candidate.split())
    return None


def _build_status_line(assistant_name: str, role: str, exit_code: int) -> str:
    if exit_code != 0:
        return f"{assistant_name} belum berhasil menyelesaikan task ini"

    role_lines = {
        "reviewer": f"{assistant_name} selesai meninjau",
        "builder": f"{assistant_name} selesai mengerjakan task ini",
        "debugger": f"{assistant_name} selesai menelusuri masalah ini",
        "ops": f"{assistant_name} selesai mengecek kondisi sistem",
        "general": f"{assistant_name} selesai memproses permintaanmu",
        "chat": f"{assistant_name} selesai ngobrol di mode chat",
    }
    return role_lines.get(role, f"{assistant_name} selesai memproses task ini")


def _build_system_activity_title(
    assistant_name: str,
    request: SystemActivityRequest,
) -> str:
    if request.include_processes and request.include_logs:
        return f"Ini yang saya lihat di laptopmu, plus catatan terbaru dari {assistant_name}."
    if request.include_processes:
        return "Ini yang lagi kelihatan di laptopmu."
    return f"Ini catatan terbaru dari {assistant_name}."


def _build_system_activity_text(
    request: SystemActivityRequest,
    report: SystemActivityReport,
) -> str:
    lines: list[str] = []
    opening_line = _build_system_activity_opening_line(request, report)
    if opening_line:
        lines.append(opening_line)

    include_system_summary = request.include_logs or request.detail_hint
    if include_system_summary:
        timestamp_label = "Baru saya cek" if request.include_processes else "Baru saya ambil"
        lines.append(
            f"{timestamp_label}: {report.captured_at.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )

    if request.include_processes:
        if include_system_summary:
            lines.extend(
                [
                    "",
                    "Sekilas kondisi laptopmu:",
                    (
                        f"CPU sekitar {report.cpu_percent:.0f}%, RAM terpakai "
                        f"{_format_bytes(report.memory_used_bytes)} dari {_format_bytes(report.memory_total_bytes)} "
                        f"({report.memory_percent:.0f}%), swap {report.swap_percent:.0f}%, "
                        f"dan laptop sudah menyala sekitar {_humanize_duration(report.host_uptime_seconds)}."
                    ),
                ]
            )
        lines.extend(
            _build_process_section(
                "Yang lagi kebuka:",
                report.desktop_apps,
                report,
                is_background=False,
            )
        )
        if request.include_logs or request.detail_hint or report.background_apps:
            lines.extend(
                _build_process_section(
                    "Yang jalan di belakang layar:",
                    report.background_apps,
                    report,
                    is_background=True,
                )
            )

        if not include_system_summary:
            lines.extend(
                [
                    "",
                    f"Saya cek ini pada {report.captured_at.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}.",
                ]
            )

    if request.include_logs and report.logs is not None:
        source_text = _describe_log_source(report.logs.source)
        log_title = "Catatan terbaru dari Codi"
        if source_text:
            log_title = f"{log_title} ({source_text})"
        lines.extend(
            [
                "",
                f"{log_title}:",
                *report.logs.lines,
            ]
        )

    if report.notes:
        lines.extend(
            [
                "",
                "Catatan kecil:",
                *[f"- {note}" for note in report.notes],
            ]
        )

    return "\n".join(line.rstrip() for line in lines).strip()


def _build_system_activity_opening_line(
    request: SystemActivityRequest,
    report: SystemActivityReport,
) -> str:
    if request.include_processes:
        if report.desktop_apps:
            top_labels = [group.label for group in report.desktop_apps[:3]]
            label_text = _join_labels_naturally(top_labels)
            remaining_count = max(0, len(report.desktop_apps) - len(top_labels))
            if remaining_count:
                return (
                    f"Yang paling kelihatan sekarang ada {label_text}, "
                    f"plus {remaining_count} aplikasi lain."
                )
            return f"Yang paling kelihatan sekarang ada {label_text}."
        if report.background_apps:
            return (
                "Saya belum melihat aplikasi desktop yang benar-benar menonjol. "
                "Yang lebih kelihatan justru proses yang jalan di belakang layar."
            )
        return "Saat ini belum kelihatan ada aplikasi yang benar-benar menonjol."

    if request.include_logs and report.logs is not None:
        return "Saya ambil catatan terbaru dari Codi di bawah ini."

    return ""


def _build_process_section(
    title: str,
    groups: tuple[ProcessGroupSummary, ...],
    report: SystemActivityReport,
    *,
    is_background: bool,
) -> list[str]:
    lines = ["", title]
    if not groups:
        if is_background:
            lines.append("- Belum ada proses latar belakang yang benar-benar menonjol saat saya cek.")
        else:
            lines.append("- Saat saya cek, belum ada aplikasi desktop yang benar-benar menonjol.")
        return lines

    for group in groups:
        lines.append(_build_process_summary_line(group, report, is_background=is_background))
    return lines


def _build_process_summary_line(
    group: ProcessGroupSummary,
    report: SystemActivityReport,
    *,
    is_background: bool,
) -> str:
    details: list[str] = []
    age_seconds = _group_age_seconds(group, report)

    if group.process_count > 1:
        details.append(f"terdiri dari {group.process_count} proses")
    if group.total_memory_bytes > 0:
        details.append(f"memakai sekitar {_format_bytes(group.total_memory_bytes)} RAM")
    if age_seconds > 0:
        if is_background:
            details.append(f"sudah berjalan sekitar {_humanize_duration(age_seconds)}")
        else:
            details.append(f"terlihat aktif sekitar {_humanize_duration(age_seconds)}")
    if group.tracked_by_codi:
        details.append("dibuka lewat Codi")

    other_users = tuple(
        username
        for username in group.usernames
        if username and username != report.current_user
    )
    if other_users:
        details.append(f"jalan atas nama akun {', '.join(other_users)}")

    if not details:
        return f"- {group.label}: terdeteksi saat pengecekan."

    return f"- {group.label}: {', '.join(details)}."


def _describe_log_source(source: str) -> str:
    if source.startswith("file:"):
        return "diambil dari file log lokal"
    if source.startswith("journal:"):
        return "diambil dari service log"
    return ""


def _join_labels_naturally(labels: list[str]) -> str:
    cleaned = [label.strip() for label in labels if label.strip()]
    if not cleaned:
        return "beberapa aplikasi"
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} dan {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, dan {cleaned[-1]}"


def _normalize_output(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").replace("```", "").replace("**", "")
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = "\n".join(line.rstrip() for line in cleaned.splitlines())
    return cleaned.strip()


def _build_preview_text(text: str, max_lines: int = 8, max_chars: int = 900) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    preview = "\n".join(lines[:max_lines]).strip()
    if len(preview) > max_chars:
        preview = preview[: max_chars - 3].rstrip() + "..."
    return preview or "Output cukup panjang, jadi saya kirim versi lengkapnya sebagai file."


def _group_age_seconds(group: ProcessGroupSummary, report: SystemActivityReport) -> int:
    if group.oldest_create_time <= 0:
        return 0
    captured_at_ts = report.captured_at.timestamp()
    return max(0, int(captured_at_ts - group.oldest_create_time))


def _humanize_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} detik"
    minutes, remaining_seconds = divmod(seconds, 60)
    hours, remaining_minutes = divmod(minutes, 60)
    days, remaining_hours = divmod(hours, 24)

    parts: list[str] = []
    if days:
        parts.append(f"{days} hari")
    if remaining_hours:
        parts.append(f"{remaining_hours} jam")
    if remaining_minutes:
        parts.append(f"{remaining_minutes} menit")
    if not parts:
        parts.append(f"{remaining_seconds} detik")
    return " ".join(parts[:2])


def _format_bytes(value: int) -> str:
    if value >= 1024 ** 3:
        return f"{value / (1024 ** 3):.1f} GB"
    if value >= 1024 ** 2:
        return f"{value / (1024 ** 2):.0f} MB"
    if value >= 1024:
        return f"{value / 1024:.0f} KB"
    return f"{value} B"
