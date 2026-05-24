import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pretty_dio_logger/pretty_dio_logger.dart';

import '../config/env.dart';
import '../providers/token_store.dart';
import 'interceptors/auth_interceptor.dart';

/// Dio terkonfigurasi untuk backend Codi.
///
/// Base URL dari [Env], timeout 30s, header client, auth interceptor,
/// logger (non-prod). Retry sederhana ditangani di repository/controller.
Dio buildDio(TokenStore tokenStore) {
  final dio = Dio(
    BaseOptions(
      baseUrl: Env.apiBaseUrl,
      connectTimeout: const Duration(seconds: 30),
      receiveTimeout: const Duration(seconds: 30),
      sendTimeout: const Duration(seconds: 30),
      headers: Env.clientHeaders,
      contentType: 'application/json',
    ),
  );

  dio.interceptors.add(AuthInterceptor(tokenStore));

  if (Env.enableLogging) {
    dio.interceptors.add(
      PrettyDioLogger(
        requestHeader: false,
        requestBody: true,
        responseBody: false,
        compact: true,
      ),
    );
  }

  return dio;
}

/// Provider instance Dio (singleton).
final dioProvider = Provider<Dio>((ref) {
  return buildDio(ref.read(tokenStoreProvider));
});
