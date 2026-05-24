import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../config/env.dart';
import '../../providers/token_store.dart';
import '../api_client.dart';
import '../api_exception.dart';

/// Akses endpoint auth (`docs/04-API-CONTRACT.md` → Authentication).
///
/// Fase A1: `/auth/login` mengembalikan shared-token sebagai access_token.
class AuthRepository {
  AuthRepository(this._dio, this._tokenStore);

  final Dio _dio;
  final TokenStore _tokenStore;

  /// Login device → simpan token. Throw [ApiException] jika gagal.
  Future<void> login({
    required String deviceId,
    required String platform,
  }) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/auth/login',
        // Login belum punya token — lewati auth interceptor. Tapi stub
        // server butuh tak ada token; bila bootstrap token ada, server
        // tetap menerima (login no-auth).
        options: Options(extra: {'skipAuth': true}),
        data: {
          'device_id': deviceId,
          'platform': platform,
          'app_version': '1.0.0',
        },
      );
      final data = res.data ?? const {};
      final token = (data['access_token'] ?? '').toString();
      if (token.isEmpty) {
        throw const ApiException(
          kind: ApiErrorKind.server,
          message: 'Server tidak mengembalikan token.',
        );
      }
      await _tokenStore.save(
        accessToken: token,
        refreshToken: data['refresh_token']?.toString(),
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> logout() async {
    try {
      await _dio.post<void>('/auth/logout');
    } on DioException {
      // Logout best-effort — tetap clear token lokal.
    } finally {
      await _tokenStore.clear();
    }
  }
}

/// Provider repository auth.
final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return AuthRepository(
    ref.read(dioProvider),
    ref.read(tokenStoreProvider),
  );
});

/// Bootstrap token (Fase A1 shared-token via --dart-define) — kalau ada,
/// langsung simpan agar request authed bisa jalan sebelum login.
Future<void> applyBootstrapToken(TokenStore store) async {
  if (Env.bootstrapToken.isNotEmpty && !store.hasToken) {
    await store.save(accessToken: Env.bootstrapToken);
  }
}
