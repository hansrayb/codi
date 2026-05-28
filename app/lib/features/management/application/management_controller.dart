import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api/api_exception.dart';
import '../../../api/repositories/management_repository.dart';
import '../domain/account.dart';
import '../domain/management_state.dart';

/// Controller untuk S7 Management.
///
/// Fetch list akun + roles saat init. Mutation (create/update/delete) refresh
/// list dari server (simple, no optimistic update di Fase C MVP).
class ManagementController extends Notifier<ManagementState> {
  @override
  ManagementState build() {
    Future.microtask(refresh);
    return const ManagementLoading();
  }

  ManagementRepository get _repo => ref.read(managementRepositoryProvider);

  Future<void> refresh() async {
    state = const ManagementLoading();
    try {
      final accounts = await _repo.listAccounts();
      final roles = await _repo.listRoles();
      state = ManagementSuccess(accounts: accounts, roles: roles);
    } on ApiException catch (e) {
      state = ManagementError(e.message);
    }
  }

  void setFilter(String roleSlug) {
    final s = state;
    if (s is ManagementSuccess) {
      state = s.copyWith(filter: roleSlug);
    }
  }

  /// Create — return null kalau sukses, pesan error kalau gagal.
  Future<String?> create({
    required String email,
    required String password,
    required String name,
    required String title,
    required String role,
  }) async {
    try {
      await _repo.createAccount(
        email: email,
        password: password,
        name: name,
        title: title,
        role: role,
      );
      await refresh();
      return null;
    } on ApiException catch (e) {
      return e.message;
    }
  }

  Future<String?> updateRole(String accountId, String role) async {
    try {
      final updated = await _repo.updateRole(accountId, role);
      _patchAccount(updated);
      return null;
    } on ApiException catch (e) {
      return e.message;
    }
  }

  Future<String?> toggleStatus(ManagedAccount account) async {
    final next = account.isActive ? 'suspended' : 'active';
    try {
      final updated = await _repo.updateStatus(account.id, next);
      _patchAccount(updated);
      return null;
    } on ApiException catch (e) {
      return e.message;
    }
  }

  Future<String?> resetPassword(String accountId, String newPassword) async {
    try {
      await _repo.resetPassword(accountId, newPassword);
      return null;
    } on ApiException catch (e) {
      return e.message;
    }
  }

  Future<String?> delete(String accountId) async {
    try {
      await _repo.deleteAccount(accountId);
      final s = state;
      if (s is ManagementSuccess) {
        state = s.copyWith(
          accounts: s.accounts.where((a) => a.id != accountId).toList(),
        );
      }
      return null;
    } on ApiException catch (e) {
      return e.message;
    }
  }

  void _patchAccount(ManagedAccount updated) {
    final s = state;
    if (s is! ManagementSuccess) return;
    state = s.copyWith(
      accounts: s.accounts
          .map((a) => a.id == updated.id ? updated : a)
          .toList(),
    );
  }
}

final managementControllerProvider =
    NotifierProvider<ManagementController, ManagementState>(
  ManagementController.new,
);
