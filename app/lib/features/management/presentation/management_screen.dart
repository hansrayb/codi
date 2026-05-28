import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers/token_store.dart';
import '../../../theme/app_theme.dart';
import '../../../widgets/emas_error_view.dart';
import '../application/management_controller.dart';
import '../domain/account.dart';
import '../domain/management_state.dart';
import 'widgets/account_card.dart';
import 'widgets/account_detail_sheet.dart';
import 'widgets/create_account_sheet.dart';

/// S7 — Management (Kelola Akun) — sub-page Profile.
///
/// CRUD akun direksi/admin. Gate scope `accounts:read` (visibility row di
/// Profile). Mutation gating dilakukan widget-level (canUpdate/canDelete)
/// + server akan reject kalau client bypass.
class ManagementScreen extends ConsumerWidget {
  const ManagementScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(managementControllerProvider);
    final ctrl = ref.read(managementControllerProvider.notifier);
    final tokenStore = ref.read(tokenStoreProvider);
    final c = context.colors;

    final canCreate = tokenStore.hasScope('accounts:create');
    final canUpdate = tokenStore.hasScope('accounts:update') ||
        tokenStore.hasScope('accounts:update_role');
    final canDelete = tokenStore.hasScope('accounts:delete');
    final selfId = tokenStore.accountId;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Kelola Akun'),
        backgroundColor: c.bgApp,
        actions: [
          if (canCreate && state is ManagementSuccess)
            IconButton(
              tooltip: 'Tambah akun',
              icon: const Icon(Icons.person_add_alt_1),
              onPressed: () => _openCreateSheet(context, ctrl, state.roles),
            ),
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(Icons.refresh),
            onPressed: ctrl.refresh,
          ),
        ],
      ),
      body: switch (state) {
        ManagementLoading() => const Center(child: CircularProgressIndicator()),
        ManagementError(:final message) => EmasErrorView(
            message: message,
            onRetry: ctrl.refresh,
          ),
        ManagementSuccess() => _ListView(
            state: state,
            canUpdate: canUpdate,
            canDelete: canDelete,
            selfId: selfId,
            ctrl: ctrl,
          ),
      },
    );
  }

  Future<void> _openCreateSheet(
    BuildContext context,
    ManagementController ctrl,
    List<ManagedRole> roles,
  ) async {
    await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => CreateAccountSheet(
        roles: roles,
        onSubmit: ctrl.create,
      ),
    );
  }
}

class _ListView extends StatelessWidget {
  const _ListView({
    required this.state,
    required this.canUpdate,
    required this.canDelete,
    required this.selfId,
    required this.ctrl,
  });

  final ManagementSuccess state;
  final bool canUpdate;
  final bool canDelete;
  final String selfId;
  final ManagementController ctrl;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final visible = state.visible;
    return RefreshIndicator(
      onRefresh: ctrl.refresh,
      child: ListView(
        padding: const EdgeInsets.only(bottom: AppSpacing.s24),
        children: [
          _FilterRow(
            roles: state.roles,
            selected: state.filter,
            onSelect: ctrl.setFilter,
          ),
          if (visible.isEmpty)
            Padding(
              padding: const EdgeInsets.all(AppSpacing.s40),
              child: Text(
                'Tak ada akun pada filter ini.',
                textAlign: TextAlign.center,
                style: AppTypography.bodyM.copyWith(color: c.inkMuted),
              ),
            )
          else
            ...visible.map(
              (acc) => AccountCard(
                account: acc,
                onTap: () => _openDetail(context, acc),
              ),
            ),
        ],
      ),
    );
  }

  void _openDetail(BuildContext context, ManagedAccount acc) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => AccountDetailSheet(
        account: acc,
        roles: state.roles,
        canUpdate: canUpdate,
        canDelete: canDelete,
        isSelf: acc.id == selfId,
        onUpdateRole: (role) => ctrl.updateRole(acc.id, role),
        onToggleStatus: () => ctrl.toggleStatus(acc),
        onResetPassword: (pw) => ctrl.resetPassword(acc.id, pw),
        onDelete: () => ctrl.delete(acc.id),
      ),
    );
  }
}

class _FilterRow extends StatelessWidget {
  const _FilterRow({
    required this.roles,
    required this.selected,
    required this.onSelect,
  });

  final List<ManagedRole> roles;
  final String selected;
  final ValueChanged<String> onSelect;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.s16,
        AppSpacing.s12,
        AppSpacing.s16,
        AppSpacing.s12,
      ),
      child: Row(
        children: [
          _Chip(label: 'Semua', active: selected.isEmpty, onTap: () => onSelect('')),
          for (final r in roles) ...[
            const SizedBox(width: AppSpacing.s8),
            _Chip(
              label: r.name,
              active: selected == r.slug,
              onTap: () => onSelect(r.slug),
            ),
          ],
        ],
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  const _Chip({required this.label, required this.active, required this.onTap});
  final String label;
  final bool active;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.s12,
          vertical: AppSpacing.s8,
        ),
        decoration: BoxDecoration(
          color: active ? c.gold : c.bgElev,
          borderRadius: BorderRadius.circular(AppRadius.r20),
          border: Border.all(
            color: active ? c.gold : c.line,
          ),
        ),
        child: Text(
          label,
          style: AppTypography.labelS.copyWith(
            color: active ? c.bgApp : c.ink,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}
