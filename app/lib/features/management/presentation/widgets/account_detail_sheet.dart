import 'package:flutter/material.dart';

import '../../../../theme/app_theme.dart';
import '../../../../widgets/emas_button.dart';
import '../../../../widgets/emas_input.dart';
import '../../domain/account.dart';
import 'role_badge.dart';

/// Bottom sheet untuk edit satu akun (ubah role, suspend, reset pw, delete).
class AccountDetailSheet extends StatefulWidget {
  const AccountDetailSheet({
    required this.account,
    required this.roles,
    required this.canUpdate,
    required this.canDelete,
    required this.isSelf,
    required this.onUpdateRole,
    required this.onToggleStatus,
    required this.onResetPassword,
    required this.onDelete,
    super.key,
  });

  final ManagedAccount account;
  final List<ManagedRole> roles;
  final bool canUpdate;
  final bool canDelete;
  final bool isSelf;

  final Future<String?> Function(String role) onUpdateRole;
  final Future<String?> Function() onToggleStatus;
  final Future<String?> Function(String newPassword) onResetPassword;
  final Future<String?> Function() onDelete;

  @override
  State<AccountDetailSheet> createState() => _AccountDetailSheetState();
}

class _AccountDetailSheetState extends State<AccountDetailSheet> {
  late String _role;
  bool _busy = false;
  String? _error;
  String? _success;

  bool get _canMutateThis =>
      widget.canUpdate && !widget.isSelf && !widget.account.isSuperadmin;

  @override
  void initState() {
    super.initState();
    _role = widget.account.role;
  }

  Future<void> _run(Future<String?> Function() task, {String? okMsg}) async {
    setState(() {
      _busy = true;
      _error = null;
      _success = null;
    });
    final err = await task();
    if (!mounted) return;
    setState(() {
      _busy = false;
      _error = err;
      _success = err == null ? okMsg : null;
    });
  }

  Future<void> _confirmAndDelete() async {
    final c = context.colors;
    final yes = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: c.bgElev,
        title: Text('Hapus ${widget.account.name}?',
            style: AppTypography.headlineS),
        content: Text(
          'Akun + semua device binding akan dihapus permanen.',
          style: AppTypography.bodyM.copyWith(color: c.inkMuted),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Batal'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: Text('Hapus', style: TextStyle(color: c.red)),
          ),
        ],
      ),
    );
    if (yes != true) return;
    final err = await widget.onDelete();
    if (!mounted) return;
    if (err == null) {
      Navigator.of(context).pop();
      return;
    }
    setState(() => _error = err);
  }

  Future<void> _resetPasswordDialog() async {
    final c = context.colors;
    final ctrl = TextEditingController();
    final newPw = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: c.bgElev,
        title: Text('Reset password', style: AppTypography.headlineS),
        content: EmasInput(
          controller: ctrl,
          hintText: 'Password baru (min 8 char)',
          obscureText: true,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Batal'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, ctrl.text),
            child: const Text('Simpan'),
          ),
        ],
      ),
    );
    if (newPw == null || newPw.isEmpty) return;
    await _run(
      () => widget.onResetPassword(newPw),
      okMsg: 'Password diubah.',
    );
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final acc = widget.account;
    return SafeArea(
      child: Container(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.s20,
          AppSpacing.s12,
          AppSpacing.s20,
          AppSpacing.s20,
        ),
        decoration: BoxDecoration(
          color: c.bgApp,
          borderRadius: const BorderRadius.vertical(
            top: Radius.circular(AppRadius.r20),
          ),
        ),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            mainAxisSize: MainAxisSize.min,
            children: [
              _Handle(color: c),
              const SizedBox(height: AppSpacing.s8),
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(acc.name,
                            style: AppTypography.headlineS.copyWith(color: c.ink)),
                        Text(acc.email,
                            style: AppTypography.bodyS
                                .copyWith(color: c.inkMuted)),
                      ],
                    ),
                  ),
                  RoleBadge(acc.role),
                ],
              ),
              const SizedBox(height: AppSpacing.s20),

              const _SectionLabel('Role'),
              const SizedBox(height: AppSpacing.s8),
              _RoleSelect(
                roles: widget.roles,
                selected: _role,
                enabled: _canMutateThis && !_busy,
                onChanged: (v) => setState(() => _role = v),
              ),
              if (_role != acc.role) ...[
                const SizedBox(height: AppSpacing.s8),
                EmasButton(
                  label: 'Simpan role',
                  expand: true,
                  onPressed: _busy
                      ? null
                      : () => _run(() => widget.onUpdateRole(_role),
                          okMsg: 'Role diubah.'),
                ),
              ],

              const SizedBox(height: AppSpacing.s20),
              const _SectionLabel('Status'),
              const SizedBox(height: AppSpacing.s8),
              EmasButton(
                label: acc.isActive ? 'Suspend akun' : 'Aktifkan akun',
                icon: acc.isActive
                    ? Icons.pause_circle_outline
                    : Icons.play_circle_outline,
                expand: true,
                variant: EmasButtonVariant.secondary,
                onPressed: (_busy || !_canMutateThis)
                    ? null
                    : () => _run(widget.onToggleStatus,
                        okMsg: acc.isActive
                            ? 'Akun di-suspend.'
                            : 'Akun aktif kembali.'),
              ),

              const SizedBox(height: AppSpacing.s20),
              const _SectionLabel('Keamanan'),
              const SizedBox(height: AppSpacing.s8),
              EmasButton(
                label: 'Reset password',
                icon: Icons.key_outlined,
                expand: true,
                variant: EmasButtonVariant.secondary,
                onPressed: (_busy || !widget.canUpdate)
                    ? null
                    : _resetPasswordDialog,
              ),

              if (widget.canDelete && !acc.isSuperadmin && !widget.isSelf) ...[
                const SizedBox(height: AppSpacing.s20),
                const _SectionLabel('Zona bahaya', danger: true),
                const SizedBox(height: AppSpacing.s8),
                EmasButton(
                  label: 'Hapus akun',
                  icon: Icons.delete_outline,
                  expand: true,
                  variant: EmasButtonVariant.secondary,
                  onPressed: _busy ? null : _confirmAndDelete,
                ),
              ],

              if (_error != null) ...[
                const SizedBox(height: AppSpacing.s12),
                Text(_error!,
                    style: AppTypography.bodyS.copyWith(color: c.red)),
              ],
              if (_success != null) ...[
                const SizedBox(height: AppSpacing.s12),
                Text(_success!,
                    style: AppTypography.bodyS.copyWith(color: c.green)),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text, {this.danger = false});
  final String text;
  final bool danger;
  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Text(
      text.toUpperCase(),
      style: AppTypography.labelS.copyWith(
        color: danger ? c.red : c.inkFaint,
        letterSpacing: 1.2,
        fontWeight: FontWeight.w700,
      ),
    );
  }
}

class _RoleSelect extends StatelessWidget {
  const _RoleSelect({
    required this.roles,
    required this.selected,
    required this.enabled,
    required this.onChanged,
  });
  final List<ManagedRole> roles;
  final String selected;
  final bool enabled;
  final ValueChanged<String> onChanged;
  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Opacity(
      opacity: enabled ? 1 : 0.5,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.s12),
        decoration: BoxDecoration(
          color: c.bgInput,
          borderRadius: BorderRadius.circular(AppRadius.r12),
          border: Border.all(color: c.lineStrong),
        ),
        child: DropdownButton<String>(
          value: roles.any((r) => r.slug == selected) ? selected : null,
          isExpanded: true,
          underline: const SizedBox.shrink(),
          dropdownColor: c.bgElev,
          items: roles
              .map((r) => DropdownMenuItem(
                    value: r.slug,
                    child: Text(r.name,
                        style: AppTypography.bodyM.copyWith(color: c.ink)),
                  ))
              .toList(),
          onChanged: enabled
              ? (v) {
                  if (v != null) onChanged(v);
                }
              : null,
        ),
      ),
    );
  }
}

class _Handle extends StatelessWidget {
  const _Handle({required this.color});
  final AppColors color;
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Container(
        width: 36,
        height: 4,
        decoration: BoxDecoration(
          color: color.line,
          borderRadius: BorderRadius.circular(2),
        ),
      ),
    );
  }
}
