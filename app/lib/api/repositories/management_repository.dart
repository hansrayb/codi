import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/management/domain/account.dart';
import '../api_client.dart';
import '../api_exception.dart';

/// Akses endpoint `/accounts/*` (`docs/04-API-CONTRACT.md` § 1b).
///
/// RBAC sudah dicek server-side; client cuma propagate error.
class ManagementRepository {
  ManagementRepository(this._dio);

  final Dio _dio;

  Future<List<ManagedAccount>> listAccounts() async {
    try {
      final res = await _dio.get<Map<String, dynamic>>('/accounts');
      final data = res.data ?? const {};
      final raw = data['accounts'] as List? ?? const [];
      return raw
          .whereType<Map<dynamic, dynamic>>()
          .map((m) => ManagedAccount.fromJson(m.cast<String, dynamic>()))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<List<ManagedRole>> listRoles() async {
    try {
      final res = await _dio.get<Map<String, dynamic>>('/accounts/roles');
      final data = res.data ?? const {};
      final raw = data['roles'] as List? ?? const [];
      return raw
          .whereType<Map<dynamic, dynamic>>()
          .map((m) => ManagedRole.fromJson(m.cast<String, dynamic>()))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<ManagedAccount> createAccount({
    required String email,
    required String password,
    required String name,
    required String title,
    required String role,
  }) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/accounts',
        data: {
          'email': email.trim().toLowerCase(),
          'password': password,
          'name': name.trim(),
          'title': title.trim(),
          'role': role,
        },
      );
      return ManagedAccount.fromJson((res.data ?? const {}));
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<ManagedAccount> updateRole(String accountId, String role) async {
    try {
      final res = await _dio.patch<Map<String, dynamic>>(
        '/accounts/$accountId/role',
        data: {'role': role},
      );
      return ManagedAccount.fromJson(res.data ?? const {});
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<ManagedAccount> updateStatus(String accountId, String status) async {
    try {
      final res = await _dio.patch<Map<String, dynamic>>(
        '/accounts/$accountId/status',
        data: {'status': status},
      );
      return ManagedAccount.fromJson(res.data ?? const {});
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> resetPassword(String accountId, String newPassword) async {
    try {
      await _dio.patch<Map<String, dynamic>>(
        '/accounts/$accountId/password',
        data: {'password': newPassword},
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> deleteAccount(String accountId) async {
    try {
      await _dio.delete<void>('/accounts/$accountId');
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

final managementRepositoryProvider = Provider<ManagementRepository>((ref) {
  return ManagementRepository(ref.read(dioProvider));
});
