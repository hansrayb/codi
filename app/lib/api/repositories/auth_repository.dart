import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../config/env.dart';
import '../../providers/token_store.dart';
import '../api_client.dart';
import '../api_exception.dart';

/// Hasil sukses login (untuk return ke controller).
class AuthLoginResult {
  const AuthLoginResult({
    required this.accountId,
    required this.email,
    required this.name,
    required this.title,
    required this.role,
    required this.scopes,
  });

  final String accountId;
  final String email;
  final String name;
  final String title;
  final String role;
  final List<String> scopes;
}

/// Akses endpoint auth (`docs/04-API-CONTRACT.md` → Authentication).
///
/// Fase B: account-based JWT (email + password) dengan enroll biometric
/// untuk login berikutnya. Bootstrap shared-token fallback untuk Fase A1.
class AuthRepository {
  AuthRepository(this._dio, this._tokenStore);

  final Dio _dio;
  final TokenStore _tokenStore;

  /// Login email + password → simpan token + scopes.
  Future<AuthLoginResult> loginEmail({
    required String email,
    required String password,
  }) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/auth/login',
        options: Options(extra: {'skipAuth': true}),
        data: {
          'email': email.trim().toLowerCase(),
          'password': password,
        },
      );
      return _persistLogin(res.data ?? const {});
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// Login biometric → server cocokkan device_fingerprint → JWT.
  Future<AuthLoginResult> loginBiometric({
    required String deviceId,
    required String deviceFingerprint,
  }) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/auth/login-biometric',
        options: Options(extra: {'skipAuth': true}),
        data: {
          'device_id': deviceId,
          'device_fingerprint': deviceFingerprint,
        },
      );
      return _persistLogin(res.data ?? const {});
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// Enroll device fingerprint ke akun yg sedang login (token Bearer wajib).
  Future<void> enrollBiometric({
    required String deviceId,
    required String deviceFingerprint,
    required String platform,
  }) async {
    try {
      await _dio.post<Map<String, dynamic>>(
        '/auth/enroll-biometric',
        data: {
          'device_id': deviceId,
          'device_fingerprint': deviceFingerprint,
          'platform': platform,
        },
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// Refresh access token.
  Future<AuthLoginResult> refresh(String refreshToken) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/auth/refresh',
        options: Options(extra: {'skipAuth': true}),
        data: {'refresh_token': refreshToken},
      );
      return _persistLogin(res.data ?? const {});
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> logout() async {
    try {
      await _dio.post<void>('/auth/logout');
    } on DioException {
      // best-effort
    } finally {
      await _tokenStore.clear();
    }
  }

  AuthLoginResult _persistLogin(Map<String, dynamic> data) {
    final token = (data['access_token'] ?? '').toString();
    if (token.isEmpty) {
      throw const ApiException(
        kind: ApiErrorKind.server,
        message: 'Server tidak mengembalikan token.',
      );
    }
    final user = (data['user'] as Map?)?.cast<String, dynamic>() ?? const {};
    final scopesRaw = data['scopes'];
    final scopes = scopesRaw is List
        ? scopesRaw.map((e) => e.toString()).toList()
        : <String>[];
    final result = AuthLoginResult(
      accountId: (user['id'] ?? '').toString(),
      email: (user['email'] ?? '').toString(),
      name: (user['name'] ?? '').toString(),
      title: (user['title'] ?? '').toString(),
      role: (user['role'] ?? '').toString(),
      scopes: scopes,
    );
    // Fire-and-forget save (caller bisa await sebelum navigasi via tokenStore).
    _tokenStore.saveSession(
      accessToken: token,
      refreshToken: data['refresh_token']?.toString(),
      scopes: scopes,
      role: result.role,
      email: result.email,
      accountId: result.accountId,
      name: result.name,
      title: result.title,
    );
    return result;
  }
}

/// Provider repository auth.
final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return AuthRepository(
    ref.read(dioProvider),
    ref.read(tokenStoreProvider),
  );
});

/// Bootstrap token (Fase A1 shared-token via --dart-define) — kalau ada
/// DAN belum ada token sesi, langsung simpan agar request authed bisa jalan
/// sebelum login. Berguna untuk QA/dev tanpa harus login dulu.
Future<void> applyBootstrapToken(TokenStore store) async {
  if (Env.bootstrapToken.isNotEmpty && !store.hasToken) {
    await store.save(accessToken: Env.bootstrapToken);
  }
}
