import 'package:flutter/foundation.dart';

import 'account.dart';

/// State sealed untuk Management screen (S7).
@immutable
sealed class ManagementState {
  const ManagementState();
}

class ManagementLoading extends ManagementState {
  const ManagementLoading();
}

class ManagementSuccess extends ManagementState {
  const ManagementSuccess({
    required this.accounts,
    required this.roles,
    this.filter = '',
  });

  /// Semua akun.
  final List<ManagedAccount> accounts;

  /// Role tersedia (untuk dropdown).
  final List<ManagedRole> roles;

  /// Filter role slug aktif ('' = semua).
  final String filter;

  /// Hasil filter.
  List<ManagedAccount> get visible {
    if (filter.isEmpty) return accounts;
    return accounts.where((a) => a.role == filter).toList();
  }

  ManagementSuccess copyWith({
    List<ManagedAccount>? accounts,
    List<ManagedRole>? roles,
    String? filter,
  }) {
    return ManagementSuccess(
      accounts: accounts ?? this.accounts,
      roles: roles ?? this.roles,
      filter: filter ?? this.filter,
    );
  }
}

class ManagementError extends ManagementState {
  const ManagementError(this.message);
  final String message;
}
