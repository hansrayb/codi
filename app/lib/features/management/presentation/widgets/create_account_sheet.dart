import 'package:flutter/material.dart';

import '../../../../theme/app_theme.dart';
import '../../../../widgets/emas_button.dart';
import '../../../../widgets/emas_input.dart';
import '../../domain/account.dart';

/// Bottom sheet untuk buat akun baru.
class CreateAccountSheet extends StatefulWidget {
  const CreateAccountSheet({
    required this.roles,
    required this.onSubmit,
    super.key,
  });

  /// Role yang bisa di-assign.
  final List<ManagedRole> roles;

  /// Return null kalau sukses, pesan error kalau gagal.
  final Future<String?> Function({
    required String email,
    required String password,
    required String name,
    required String title,
    required String role,
  }) onSubmit;

  @override
  State<CreateAccountSheet> createState() => _CreateAccountSheetState();
}

class _CreateAccountSheetState extends State<CreateAccountSheet> {
  final _emailCtrl = TextEditingController();
  final _pwCtrl = TextEditingController();
  final _nameCtrl = TextEditingController();
  final _titleCtrl = TextEditingController();
  String _role = 'director';
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    if (widget.roles.any((r) => r.slug == 'director')) {
      _role = 'director';
    } else if (widget.roles.isNotEmpty) {
      _role = widget.roles.first.slug;
    }
  }

  @override
  void dispose() {
    _emailCtrl.dispose();
    _pwCtrl.dispose();
    _nameCtrl.dispose();
    _titleCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _error = null;
      _busy = true;
    });
    final err = await widget.onSubmit(
      email: _emailCtrl.text,
      password: _pwCtrl.text,
      name: _nameCtrl.text,
      title: _titleCtrl.text,
      role: _role,
    );
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
    final viewInsets = MediaQuery.viewInsetsOf(context).bottom;
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(bottom: viewInsets),
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
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _Handle(color: c),
              const SizedBox(height: AppSpacing.s8),
              Text(
                'Buat Akun Baru',
                textAlign: TextAlign.center,
                style: AppTypography.headlineS.copyWith(color: c.ink),
              ),
              const SizedBox(height: AppSpacing.s16),
              EmasInput(controller: _emailCtrl, hintText: 'Email'),
              const SizedBox(height: AppSpacing.s8),
              EmasInput(
                controller: _pwCtrl,
                hintText: 'Password (min 8 char)',
                obscureText: true,
              ),
              const SizedBox(height: AppSpacing.s8),
              EmasInput(controller: _nameCtrl, hintText: 'Nama lengkap'),
              const SizedBox(height: AppSpacing.s8),
              EmasInput(
                controller: _titleCtrl,
                hintText: 'Jabatan (mis. Direktur Utama)',
              ),
              const SizedBox(height: AppSpacing.s12),
              _RoleDropdown(
                roles: widget.roles,
                selected: _role,
                onChanged: (v) => setState(() => _role = v),
              ),
              if (_error != null) ...[
                const SizedBox(height: AppSpacing.s12),
                Text(
                  _error!,
                  style: AppTypography.bodyS.copyWith(color: c.red),
                ),
              ],
              const SizedBox(height: AppSpacing.s20),
              EmasButton(
                label: _busy ? 'Menyimpan...' : 'Simpan',
                expand: true,
                onPressed: _busy ? null : _submit,
              ),
              const SizedBox(height: AppSpacing.s8),
              EmasButton(
                label: 'Batal',
                expand: true,
                variant: EmasButtonVariant.secondary,
                onPressed: _busy ? null : () => Navigator.of(context).pop(false),
              ),
            ],
          ),
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

class _RoleDropdown extends StatelessWidget {
  const _RoleDropdown({
    required this.roles,
    required this.selected,
    required this.onChanged,
  });

  final List<ManagedRole> roles;
  final String selected;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.s12),
      decoration: BoxDecoration(
        color: c.bgInput,
        borderRadius: BorderRadius.circular(AppRadius.r12),
        border: Border.all(color: c.lineStrong),
      ),
      child: DropdownButton<String>(
        value: selected,
        isExpanded: true,
        underline: const SizedBox.shrink(),
        dropdownColor: c.bgElev,
        items: roles
            .map((r) => DropdownMenuItem(
                  value: r.slug,
                  child: Text(
                    r.name,
                    style: AppTypography.bodyM.copyWith(color: c.ink),
                  ),
                ))
            .toList(),
        onChanged: (v) {
          if (v != null) onChanged(v);
        },
      ),
    );
  }
}
