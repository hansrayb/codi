import 'package:flutter/foundation.dart';

/// Akun direksi/admin dari backend Codi (`/accounts`).
@immutable
class ManagedAccount {
  const ManagedAccount({
    required this.id,
    required this.email,
    required this.name,
    required this.title,
    required this.role,
    required this.status,
    this.createdAt,
    this.lastLoginAt,
  });

  factory ManagedAccount.fromJson(Map<String, dynamic> json) => ManagedAccount(
        id: (json['id'] ?? '').toString(),
        email: (json['email'] ?? '').toString(),
        name: (json['name'] ?? '').toString(),
        title: (json['title'] ?? '').toString(),
        role: (json['role'] ?? '').toString(),
        status: (json['status'] ?? 'active').toString(),
        createdAt: _parseDate(json['created_at']),
        lastLoginAt: _parseDate(json['last_login_at']),
      );

  final String id;
  final String email;
  final String name;
  final String title;
  final String role;
  final String status;
  final DateTime? createdAt;
  final DateTime? lastLoginAt;

  bool get isActive => status == 'active';
  bool get isSuperadmin => role == 'superadmin';

  static DateTime? _parseDate(Object? v) {
    if (v is! String || v.isEmpty) return null;
    return DateTime.tryParse(v);
  }
}

/// Role tersedia di server (`/accounts/roles`).
@immutable
class ManagedRole {
  const ManagedRole({
    required this.slug,
    required this.name,
    required this.scopes,
  });

  factory ManagedRole.fromJson(Map<String, dynamic> json) => ManagedRole(
        slug: (json['slug'] ?? '').toString(),
        name: (json['name'] ?? '').toString(),
        scopes: (json['scopes'] as List? ?? const [])
            .map((e) => e.toString())
            .toList(),
      );

  final String slug;
  final String name;
  final List<String> scopes;
}
