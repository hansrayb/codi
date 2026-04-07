"""Telegram-safe formatting helpers for execution results."""

from __future__ import annotations

from html import escape
import re

from telegram.constants import ParseMode

from core.edit_approval import PendingApproval
from core.self_maintenance import SelfCheckResult
from core.system_activity import ProcessGroupSummary, SystemActivityReport
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

    status_line = _build_status_line(assistant_name, role, exit_code)
    return MessagePayload(
        text=(
            f"<b>{escape(status_line)}</b>\n\n"
            f"{escape(primary_output)}"
        ),
        parse_mode=ParseMode.HTML,
    )


def format_error_payload(message: str, *, assistant_name: str = "Codi") -> MessagePayload:
    """Return a simple HTML-safe error payload."""

    return MessagePayload(
        text=f"<b>{escape(assistant_name)} belum sempat menyelesaikan task ini.</b>\n\n{escape(message)}",
        parse_mode=ParseMode.HTML,
    )


def format_edit_approval_payload(
    *,
    assistant_name: str,
    pending: PendingApproval,
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
    text_parts.extend(
        [
            "",
            (
                "Balas <code>lanjutkan</code> untuk apply checkpoint ini, "
                "atau <code>batal</code> untuk membuang revisi terakhir dan kembali ke kondisi repo saat ini."
            ),
        ]
    )
    diff_text = pending.diff_text or "(Tidak ada diff tekstual. Perubahan mungkin file biner atau metadata.)"
    return MessagePayload(
        text="\n".join(text_parts),
        parse_mode=ParseMode.HTML,
        attachment_filename=f"{pending.approval_id}-proposal.patch",
        attachment_bytes=diff_text.encode("utf-8"),
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
    report: SystemActivityReport,
    max_output_length: int,
) -> MessagePayload:
    """Return a Telegram-safe summary of local host activity."""

    title = f"{assistant_name} melihat aktivitas laptop ini."
    body = _build_system_activity_text(report)
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


def _build_self_update_detail_text(check_result: SelfCheckResult) -> str:
    parts = [
        "[compileall]",
        check_result.compile_output.strip() or "(empty)",
        "",
        "[tests]",
        check_result.test_output.strip() or "(empty)",
    ]
    return "\n".join(parts)


def _build_status_line(assistant_name: str, role: str, exit_code: int) -> str:
    if exit_code != 0:
        return f"{assistant_name} belum berhasil menyelesaikan task ini"

    role_lines = {
        "reviewer": f"{assistant_name} selesai meninjau",
        "builder": f"{assistant_name} selesai mengerjakan task ini",
        "debugger": f"{assistant_name} selesai menelusuri masalah ini",
        "ops": f"{assistant_name} selesai mengecek kondisi sistem",
        "general": f"{assistant_name} selesai memproses permintaanmu",
    }
    return role_lines.get(role, f"{assistant_name} selesai memproses task ini")


def _build_system_activity_text(report: SystemActivityReport) -> str:
    lines = [
        f"Snapshot: {report.captured_at.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"User bot: {report.current_user}",
        "",
        "Ringkasan host:",
        f"CPU  : {report.cpu_percent:.0f}%",
        (
            "RAM  : "
            f"{_format_bytes(report.memory_used_bytes)} / {_format_bytes(report.memory_total_bytes)} "
            f"({report.memory_percent:.0f}%)"
        ),
        f"Swap : {report.swap_percent:.0f}%",
        f"Uptime host: {_humanize_duration(report.host_uptime_seconds)}",
    ]

    lines.extend(_build_process_section("Aplikasi desktop aktif:", report.desktop_apps, report))
    lines.extend(_build_process_section("Background atau service menonjol:", report.background_apps, report))

    if report.logs is not None:
        lines.extend(
            [
                "",
                f"Log terbaru ({report.logs.source}):",
                *report.logs.lines,
            ]
        )

    if report.notes:
        lines.extend(
            [
                "",
                "Catatan:",
                *[f"- {note}" for note in report.notes],
            ]
        )

    return "\n".join(line.rstrip() for line in lines).strip()


def _build_process_section(
    title: str,
    groups: tuple[ProcessGroupSummary, ...],
    report: SystemActivityReport,
) -> list[str]:
    lines = ["", title]
    if not groups:
        lines.append("- Tidak ada item yang menonjol saat snapshot diambil.")
        return lines

    for group in groups:
        flags: list[str] = []
        if group.tracked_by_codi:
            flags.append("dibuka oleh Codi")
        if group.usernames:
            flags.append(f"user: {', '.join(group.usernames)}")
        age_seconds = _group_age_seconds(group, report)
        lines.append(
            " | ".join(
                [
                    f"- {group.label}",
                    f"{group.process_count} proses",
                    f"RAM {_format_bytes(group.total_memory_bytes)}",
                    f"uptime {_humanize_duration(age_seconds)}",
                    group.status_summary,
                    f"pid contoh {group.sample_pid}",
                    *flags,
                ]
            )
        )
        if group.sample_command:
            lines.append(f"  cmd: {group.sample_command}")
    return lines


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
