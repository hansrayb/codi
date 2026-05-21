"""Device-registry handler mixin for the Codi orchestrator."""

from __future__ import annotations

from html import escape

from core.device_tasks import (
    classify_device_task_for_dispatch,
    is_active_device_query,
    parse_device_context_status_request,
    parse_device_repo_request,
    parse_explicit_device_request,
    parse_task_status_request,
    parse_use_device_request,
    parse_use_host_request,
    required_capability_for_task,
)
from models.result import MessagePayload
from utils.formatter import format_error_payload


class DeviceHandlerMixin:
    """Mixin providing device-registry query handling."""

    async def try_handle_device_message(
        self,
        user_id: int,
        text: str,
    ) -> MessagePayload | None:
        """Handle device-registry queries without invoking Claude."""

        task_status_id = parse_task_status_request(text)
        if task_status_id is not None and self._device_task_queue is not None:
            return self._device_task_queue.render_task_payload(
                task_status_id,
                assistant_name=self._settings.assistant_name,
            )

        use_device_ref = parse_use_device_request(text)
        if use_device_ref is not None:
            return self._set_active_device(user_id, use_device_ref)

        if parse_use_host_request(text):
            return self._set_host_target(user_id)

        if is_active_device_query(text):
            return self._render_active_device(user_id)

        repo_request = parse_device_repo_request(text)
        if repo_request is not None:
            device_ref, repo_path = repo_request
            return self._set_device_repo(user_id, device_ref, repo_path)

        context_device_ref = parse_device_context_status_request(text)
        if context_device_ref is not None:
            return self._render_device_context(user_id, context_device_ref)

        explicit_request = parse_explicit_device_request(text)
        if explicit_request is not None:
            return self._handle_explicit_device_task(
                user_id,
                explicit_request.device_ref,
                explicit_request.task_text,
            )

        query = self._device_registry_manager.classify_message(text)
        if query is not None:
            if query.action == "list":
                return self._device_registry_manager.render_list_payload()
            if query.action == "detail" and query.device_ref:
                return self._device_registry_manager.render_detail_payload(query.device_ref)
            return None

        if (
            self._device_context_store is not None
            and self._device_task_queue is not None
        ):
            active_target = self._device_context_store.get_active_target(user_id)
            if active_target.target_kind == "device" and active_target.device_id:
                device = self._device_registry_manager.resolve_device(active_target.device_id)
                if device is not None and self._device_registry_manager.is_online_record(device):
                    ctx = self._device_context_store.get_context(user_id, device.device_id)
                    return self._handle_natural_device_query(user_id, device, text, ctx)

        return None

    def _set_active_device(self, user_id: int, device_ref: str) -> MessagePayload:
        if self._device_context_store is None:
            return format_error_payload("Device context store belum aktif.", assistant_name=self._settings.assistant_name)
        device = self._device_registry_manager.resolve_device(device_ref)
        if device is None:
            return format_error_payload(
                f"Saya belum menemukan device '{device_ref}'.",
                assistant_name=self._settings.assistant_name,
            )
        self._device_context_store.set_active_device(user_id, device.device_id)
        context = self._device_context_store.get_context(user_id, device.device_id)
        repo_line = f"\nRepo aktif: <code>{escape(context.active_repo)}</code>" if context.active_repo else ""
        return MessagePayload(
            text=(
                f"<b>{escape(self._settings.assistant_name)} memakai device aktif.</b>\n\n"
                f"Device: <code>{escape(device.label)}</code> (<code>{escape(device.device_id)}</code>){repo_line}"
            ),
            parse_mode="HTML",
        )

    def _set_host_target(self, user_id: int) -> MessagePayload:
        if self._device_context_store is None:
            return format_error_payload("Device context store belum aktif.", assistant_name=self._settings.assistant_name)
        self._device_context_store.set_host_target(user_id)
        return MessagePayload(
            text=(
                f"<b>{escape(self._settings.assistant_name)} memakai host pusat.</b>\n\n"
                "Prompt berikutnya akan dijalankan di komputer induk sampai target diganti lagi."
            ),
            parse_mode="HTML",
        )

    def _render_active_device(self, user_id: int) -> MessagePayload:
        if self._device_context_store is None:
            return format_error_payload("Device context store belum aktif.", assistant_name=self._settings.assistant_name)
        target = self._device_context_store.get_active_target(user_id)
        if target.target_kind == "host":
            remembered = self._device_context_store.get_active_device(user_id)
            remembered_line = ""
            if remembered:
                remembered_line = f"\nDevice terakhir dipakai: <code>{escape(remembered)}</code>"
            return MessagePayload(
                text=(
                    f"<b>{escape(self._settings.assistant_name)} target aktif sekarang host pusat.</b>\n\n"
                    f"Semua prompt biasa akan dijalankan di komputer induk.{remembered_line}"
                ),
                parse_mode="HTML",
            )
        if not target.device_id:
            return MessagePayload(
                text=(
                    f"<b>{escape(self._settings.assistant_name)}</b>\n\n"
                    "Belum ada device aktif. Gunakan <code>pakai device absen-server</code>."
                ),
                parse_mode="HTML",
            )
        return self._render_device_context(user_id, target.device_id)

    def _set_device_repo(
        self,
        user_id: int,
        device_ref: str | None,
        repo_path: str,
    ) -> MessagePayload:
        if self._device_context_store is None:
            return format_error_payload("Device context store belum aktif.", assistant_name=self._settings.assistant_name)
        resolved_device_ref = device_ref or self._device_context_store.get_active_device(user_id)
        if not resolved_device_ref:
            return format_error_payload(
                "Pilih device dulu dengan <code>pakai device absen-server</code>, atau tulis <code>di device absen-server, pakai repo /path</code>.",
                assistant_name=self._settings.assistant_name,
            )
        device = self._device_registry_manager.resolve_device(resolved_device_ref)
        if device is None:
            return format_error_payload(
                f"Saya belum menemukan device '{resolved_device_ref}'.",
                assistant_name=self._settings.assistant_name,
            )
        context = self._device_context_store.set_active_repo(user_id, device.device_id, repo_path)
        return MessagePayload(
            text=(
                f"<b>{escape(self._settings.assistant_name)} menyimpan konteks repo device.</b>\n\n"
                f"Device: <code>{escape(device.label)}</code> (<code>{escape(device.device_id)}</code>)\n"
                f"Repo aktif: <code>{escape(context.active_repo or '-')}</code>"
            ),
            parse_mode="HTML",
        )

    def _render_device_context(self, user_id: int, device_ref: str) -> MessagePayload:
        if self._device_context_store is None:
            return format_error_payload("Device context store belum aktif.", assistant_name=self._settings.assistant_name)
        device = self._device_registry_manager.resolve_device(device_ref)
        if device is None:
            return format_error_payload(
                f"Saya belum menemukan device '{device_ref}'.",
                assistant_name=self._settings.assistant_name,
            )
        context = self._device_context_store.get_context(user_id, device.device_id)
        status = "online" if self._device_registry_manager.is_online_record(device) else "offline"
        active_target = self._device_context_store.get_active_target(user_id)
        target_line = "ya" if active_target.target_kind == "device" and active_target.device_id == device.device_id else "tidak"
        return MessagePayload(
            text=(
                f"<b>Konteks device {escape(device.label)}</b>\n\n"
                f"ID: <code>{escape(device.device_id)}</code>\n"
                f"Status: {escape(status)}\n"
                f"Target aktif: {escape(target_line)}\n"
                f"Repo aktif: <code>{escape(context.active_repo or '-')}</code>"
            ),
            parse_mode="HTML",
        )

    def render_devices_panel(self, user_id: int) -> MessagePayload:
        if self._device_context_store is None:
            return format_error_payload("Device context store belum aktif.", assistant_name=self._settings.assistant_name)
        records = self._device_registry_manager.list_records()
        target = self._device_context_store.get_active_target(user_id)
        if target.target_kind == "host":
            target_summary = "Host pusat"
        elif target.device_id:
            target_summary = f"Device <code>{escape(target.device_id)}</code>"
        else:
            target_summary = "Host pusat"

        lines = [
            f"<b>{escape(self._settings.assistant_name)} target eksekusi</b>",
            "",
            f"Target aktif: {target_summary}",
            "Pilih host pusat atau salah satu device di bawah ini.",
        ]
        if not records:
            lines.extend([
                "",
                "Belum ada device yang pernah register ke bot pusat ini.",
            ])
        else:
            lines.append("")
            lines.append("Device terdaftar:")
            for record in records:
                state = "online" if self._device_registry_manager.is_online_record(record) else "offline"
                context = self._device_context_store.get_context(user_id, record.device_id)
                marker = "aktif" if target.target_kind == "device" and target.device_id == record.device_id else "-"
                lines.append(
                    (
                        f"- <b>{escape(record.label)}</b> (<code>{escape(record.device_id)}</code>) | "
                        f"{escape(state)} | target: {escape(marker)}\n"
                        f"  Repo: <code>{escape(context.active_repo or '-')}</code>"
                    )
                )

        inline_buttons = [("Host Pusat", "device:target:host"), ("Refresh", "device:panel:refresh")]
        for record in records:
            inline_buttons.append((f"Pakai {record.label}", f"device:target:{record.device_id}"))
            inline_buttons.append((f"Detail {record.label}", f"device:detail:{record.device_id}"))
        return MessagePayload(
            text="\n".join(lines),
            parse_mode="HTML",
            inline_buttons=tuple(inline_buttons),
        )

    def handle_device_panel_callback(self, user_id: int, data: str) -> MessagePayload:
        if data == "device:panel:refresh":
            return self.render_devices_panel(user_id)
        if data == "device:target:host":
            self._set_host_target(user_id)
            return self.render_devices_panel(user_id)
        if data.startswith("device:target:"):
            self._set_active_device(user_id, data[len("device:target:"):])
            return self.render_devices_panel(user_id)
        if data.startswith("device:detail:"):
            return self._render_device_context(user_id, data[len("device:detail:"):])
        return format_error_payload("Aksi device tidak dikenal.", assistant_name=self._settings.assistant_name)

    def _handle_explicit_device_task(
        self,
        user_id: int,
        device_ref: str,
        task_text: str,
    ) -> MessagePayload:
        if self._device_task_queue is None:
            return format_error_payload(
                "Device task queue belum aktif di bot pusat ini.",
                assistant_name=self._settings.assistant_name,
            )
        device = self._device_registry_manager.resolve_device(device_ref)
        if device is None:
            return format_error_payload(
                f"Saya belum menemukan device '{device_ref}'. Cek daftar dengan /devices.",
                assistant_name=self._settings.assistant_name,
            )
        if not self._device_registry_manager.is_online_record(device):
            return format_error_payload(
                f"Device {device.label} sedang offline.",
                assistant_name=self._settings.assistant_name,
            )
        context = (
            self._device_context_store.get_context(user_id, device.device_id)
            if self._device_context_store is not None
            else None
        )
        active_repo = context.active_repo if context is not None else None
        kind, task_payload = classify_device_task_for_dispatch(
            task_text,
            active_repo=active_repo,
        )
        unsupported_payload = self._device_capability_error_payload(device, kind)
        if unsupported_payload is not None:
            return unsupported_payload
        task = self._device_task_queue.enqueue(
            device_id=device.device_id,
            requested_by=user_id,
            kind=kind,
            payload=task_payload,
        )
        self._logger.info(
            "user_id=%s | action=device_task_enqueued | device=%s | task=%s | kind=%s",
            user_id,
            device.device_id,
            task.task_id,
            kind,
        )
        return self._device_task_queued_payload(device, task, kind, task_payload)

    def _device_task_queued_payload(
        self,
        device,
        task,
        kind: str,
        task_payload: dict[str, object],
    ) -> MessagePayload:
        cwd_label = str(task_payload.get("cwd") or task_payload.get("query") or "-")
        if kind in {"natural_query", "repo_readonly_query"}:
            query_preview = str(task_payload.get("query") or "")
            if len(query_preview) > 80:
                query_preview = query_preview[:77] + "..."
            repo_line = ""
            if kind == "repo_readonly_query":
                repo_line = f"\nRepo: <code>{escape(str(task_payload.get('cwd') or '-'))}</code>"
            detail_line = f"Pertanyaan: <i>{escape(query_preview)}</i>{repo_line}"
        else:
            detail_line = f"Repo context: <code>{escape(cwd_label)}</code>"
        return MessagePayload(
            text=(
                f"<b>{escape(self._settings.assistant_name)} mengirim task ke device.</b>\n\n"
                f"Device: <code>{escape(device.label)}</code> (<code>{escape(device.device_id)}</code>)\n"
                f"Task: <code>{escape(task.task_id)}</code>\n"
                f"Jenis: <code>{escape(kind)}</code>\n"
                f"{detail_line}\n\n"
                f"Cek hasil dengan <code>hasil task {escape(task.task_id)}</code>."
            ),
            parse_mode="HTML",
            inline_buttons=(("🔄 Cek Hasil", f"device:task:{task.task_id}"),),
        )

    def _handle_natural_device_query(
        self,
        user_id: int,
        device,
        query_text: str,
        context,
    ) -> MessagePayload:
        if self._device_task_queue is None:
            return format_error_payload("Device task queue belum aktif.", assistant_name=self._settings.assistant_name)
        kind, task_payload = classify_device_task_for_dispatch(
            query_text,
            active_repo=context.active_repo,
        )
        unsupported_payload = self._device_capability_error_payload(device, kind)
        if unsupported_payload is not None:
            return unsupported_payload
        task = self._device_task_queue.enqueue(
            device_id=device.device_id,
            requested_by=user_id,
            kind=kind,
            payload=task_payload,
        )
        self._logger.info(
            "user_id=%s | action=natural_device_task_enqueued | device=%s | task=%s | kind=%s",
            user_id, device.device_id, task.task_id, kind,
        )
        return self._device_task_queued_payload(device, task, kind, task_payload)

    def _device_capability_error_payload(self, device, kind: str) -> MessagePayload | None:
        required = required_capability_for_task(kind)
        if required in set(device.capabilities):
            return None
        capabilities = ", ".join(device.capabilities) if device.capabilities else "-"
        return format_error_payload(
            (
                f"Device {device.label} belum mengiklankan capability `{required}` "
                f"untuk task `{kind}`.\n\n"
                f"Capability saat ini: `{capabilities}`.\n"
                "Update dan restart agent di device itu, lalu cek `detail device` lagi."
            ),
            assistant_name=self._settings.assistant_name,
        )
