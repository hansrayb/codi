import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../../theme/app_theme.dart';
import '../../../../widgets/emas_button.dart';
import '../../../../widgets/emas_input.dart';
import '../../domain/account.dart';
import 'role_badge.dart';

/// Sheet edit profil akun — form lengkap & profesional (S7).
///
/// Identitas (nama/jabatan/email) + akses (role + preview scope) + info akun
/// read-only. Validasi nama wajib & format email. Memanggil [onUpdateProfile]
/// untuk field profil, [onUpdateRole] kalau role berubah.
class EditProfileSheet extends StatefulWidget {
  const EditProfileSheet({
    required this.account,
    required this.roles,
    required this.canMutateRole,
    required this.onUpdateProfile,
    required this.onUpdateRole,
    super.key,
  });

  final ManagedAccount account;
  final List<ManagedRole> roles;
  final bool canMutateRole;
  final Future<String?> Function({String? name, String? title, String? email})
      onUpdateProfile;
  final Future<String?> Function(String role) onUpdateRole;

  @override
  State<EditProfileSheet> createState() => _EditProfileSheetState();
}

class _EditProfileSheetState extends State<EditProfileSheet> {
  late final TextEditingController _name;
  late final TextEditingController _title;
  late final TextEditingController _email;
  late String _role;
  bool _busy = false;
  String? _error;
  String? _nameErr;
  String? _emailErr;

  @override
  void initState() {
    super.initState();
    _name = TextEditingController(text: widget.account.name);
    _title = TextEditingController(text: widget.account.title);
    _email = TextEditingController(text: widget.account.email);
    _role = widget.account.role;
  }

  @override
  void dispose() {
    _name.dispose();
    _title.dispose();
    _email.dispose();
    super.dispose();
  }

  String _initials() {
    final parts = _name.text.trim().split(RegExp(r'\s+'));
    if (parts.isEmpty || parts.first.isEmpty) return '?';
    if (parts.length == 1) return parts.first[0].toUpperCase();
    return (parts.first[0] + parts.last[0]).toUpperCase();
  }

  bool _validate() {
    final name = _name.text.trim();
    final email = _email.text.trim();
    final emailOk = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch(email);
    setState(() {
      _nameErr = name.isEmpty ? 'Nama wajib diisi.' : null;
      _emailErr = email.isEmpty
          ? 'Email wajib diisi.'
          : (emailOk ? null : 'Format email tidak valid.');
    });
    return _nameErr == null && _emailErr == null;
  }

  Future<void> _save() async {
    if (_busy || !_validate()) return;
    final acc = widget.account;
    setState(() {
      _busy = true;
      _error = null;
    });

    final name = _name.text.trim();
    final title = _title.text.trim();
    final email = _email.text.trim();
    final roleChanged = _role != acc.role;
    final profileChanged =
        name != acc.name || title != acc.title || email != acc.email;

    String? err;
    if (profileChanged) {
      err = await widget.onUpdateProfile(
        name: name != acc.name ? name : null,
        title: title != acc.title ? title : null,
        email: email != acc.email ? email : null,
      );
    }
    if (err == null && roleChanged) {
      err = await widget.onUpdateRole(_role);
    }

    if (!mounted) return;
    if (err == null) {
      Navigator.of(context).pop(true);
      return;
    }
    setState(() {
      _busy = false;
      _error = err;
    });
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final acc = widget.account;
    final maxH = MediaQuery.sizeOf(context).height * 0.9;

    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.viewInsetsOf(context).bottom,
        ),
        child: Container(
          constraints: BoxConstraints(maxHeight: maxH),
          decoration: BoxDecoration(
            color: c.bgApp,
            borderRadius: const BorderRadius.vertical(
              top: Radius.circular(AppRadius.r20),
            ),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const SizedBox(height: AppSpacing.s12),
              Center(
                child: Container(
                  width: 36,
                  height: 4,
                  decoration: BoxDecoration(
                    color: c.line,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              Flexible(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.s20,
                    AppSpacing.s16,
                    AppSpacing.s20,
                    AppSpacing.s20,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      _hero(c),
                      const SizedBox(height: AppSpacing.s20),
                      const _SectionLabel('Identitas'),
                      const SizedBox(height: AppSpacing.s10),
                      _field('Nama lengkap', _name, error: _nameErr),
                      const SizedBox(height: AppSpacing.s12),
                      _field('Jabatan', _title, hint: 'mis. Direktur Utama'),
                      const SizedBox(height: AppSpacing.s12),
                      _field('Email', _email, error: _emailErr),
                      const SizedBox(height: AppSpacing.s20),
                      const _SectionLabel('Akses'),
                      const SizedBox(height: AppSpacing.s10),
                      _roleField(c, acc),
                      const SizedBox(height: AppSpacing.s20),
                      const _SectionLabel('Info Akun'),
                      const SizedBox(height: AppSpacing.s10),
                      _infoCard(c, acc),
                      if (_error != null) ...[
                        const SizedBox(height: AppSpacing.s14),
                        Text(
                          _error!,
                          style:
                              AppTypography.bodyS.copyWith(color: c.red),
                        ),
                      ],
                      const SizedBox(height: AppSpacing.s20),
                      Row(
                        children: [
                          Expanded(
                            child: EmasButton(
                              label: 'Batal',
                              variant: EmasButtonVariant.secondary,
                              expand: true,
                              onPressed: _busy
                                  ? null
                                  : () => Navigator.of(context).pop(),
                            ),
                          ),
                          const SizedBox(width: AppSpacing.s12),
                          Expanded(
                            child: EmasButton(
                              label: _busy ? 'Menyimpan...' : 'Simpan',
                              expand: true,
                              onPressed: _busy ? null : _save,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _hero(AppColors c) {
    return Row(
      children: [
        Container(
          width: 56,
          height: 56,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: c.goldSoft,
            border: Border.all(color: c.goldLine),
          ),
          child: Text(
            _initials(),
            style: AppTypography.headlineS.copyWith(
              color: c.gold,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        const SizedBox(width: AppSpacing.s14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Edit Profil',
                style: AppTypography.headlineS.copyWith(color: c.ink),
              ),
              const SizedBox(height: 2),
              Text(
                widget.account.email,
                style: AppTypography.bodyS.copyWith(color: c.inkMuted),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
        RoleBadge(_role),
      ],
    );
  }

  Widget _field(
    String label,
    TextEditingController ctrl, {
    String? hint,
    String? error,
  }) {
    final c = context.colors;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: AppTypography.labelS.copyWith(color: c.inkMuted),
        ),
        const SizedBox(height: AppSpacing.s6),
        EmasInput(controller: ctrl, hintText: hint ?? label),
        if (error != null) ...[
          const SizedBox(height: AppSpacing.s4),
          Text(error, style: AppTypography.bodyS.copyWith(color: c.red)),
        ],
      ],
    );
  }

  Widget _roleField(AppColors c, ManagedAccount acc) {
    final selected = widget.roles.where((r) => r.slug == _role).toList();
    final scopes = selected.isEmpty ? const <String>[] : selected.first.scopes;
    final enabled = widget.canMutateRole && !acc.isSuperadmin;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Opacity(
          opacity: enabled ? 1 : 0.5,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.s12),
            decoration: BoxDecoration(
              color: c.bgInput,
              borderRadius: BorderRadius.circular(AppRadius.r12),
              border: Border.all(color: c.lineStrong),
            ),
            child: DropdownButton<String>(
              value: widget.roles.any((r) => r.slug == _role) ? _role : null,
              isExpanded: true,
              underline: const SizedBox.shrink(),
              dropdownColor: c.bgElev,
              items: widget.roles
                  .map((r) => DropdownMenuItem(
                        value: r.slug,
                        child: Text(
                          r.name,
                          style:
                              AppTypography.bodyM.copyWith(color: c.ink),
                        ),
                      ))
                  .toList(),
              onChanged: enabled
                  ? (v) {
                      if (v != null) setState(() => _role = v);
                    }
                  : null,
            ),
          ),
        ),
        if (!enabled) ...[
          const SizedBox(height: AppSpacing.s4),
          Text(
            acc.isSuperadmin
                ? 'Role superadmin tidak bisa diubah.'
                : 'Tidak punya izin ubah role.',
            style: AppTypography.bodyS.copyWith(color: c.inkFaint),
          ),
        ],
        if (scopes.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.s10),
          Text(
            'Hak akses',
            style: AppTypography.labelS.copyWith(color: c.inkMuted),
          ),
          const SizedBox(height: AppSpacing.s6),
          Wrap(
            spacing: AppSpacing.s6,
            runSpacing: AppSpacing.s6,
            children: [
              for (final s in scopes)
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.s8,
                    vertical: AppSpacing.s4,
                  ),
                  decoration: BoxDecoration(
                    color: c.bgElev,
                    borderRadius: BorderRadius.circular(AppRadius.r8),
                    border: Border.all(color: c.line),
                  ),
                  child: Text(
                    s,
                    style: AppTypography.labelS.copyWith(
                      color: c.inkDim,
                      fontSize: 10,
                    ),
                  ),
                ),
            ],
          ),
        ],
      ],
    );
  }

  Widget _infoCard(AppColors c, ManagedAccount acc) {
    String fmt(DateTime? d) =>
        d == null ? '—' : DateFormat('d MMM yyyy', 'id_ID').format(d.toLocal());
    final rows = <(String, String)>[
      ('ID Akun', acc.id),
      ('Status', acc.isActive ? 'Aktif' : 'Suspended'),
      ('Dibuat', fmt(acc.createdAt)),
      ('Login terakhir', fmt(acc.lastLoginAt)),
    ];
    return Container(
      padding: const EdgeInsets.all(AppSpacing.s16),
      decoration: BoxDecoration(
        color: c.bgCard,
        borderRadius: BorderRadius.circular(AppRadius.r16),
        border: Border.all(color: c.line),
      ),
      child: Column(
        children: [
          for (var i = 0; i < rows.length; i++) ...[
            if (i > 0) const SizedBox(height: AppSpacing.s10),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  rows[i].$1,
                  style: AppTypography.bodyS.copyWith(color: c.inkMuted),
                ),
                const SizedBox(width: AppSpacing.s12),
                Expanded(
                  child: Text(
                    rows[i].$2,
                    textAlign: TextAlign.right,
                    style: AppTypography.bodyM.copyWith(
                      color: c.ink,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text);
  final String text;
  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Text(
      text.toUpperCase(),
      style: AppTypography.labelS.copyWith(
        color: c.inkFaint,
        letterSpacing: 1.2,
        fontWeight: FontWeight.w700,
      ),
    );
  }
}
