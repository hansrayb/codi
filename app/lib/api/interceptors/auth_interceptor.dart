import 'package:dio/dio.dart';

import '../../providers/token_store.dart';

/// Menyisipkan `Authorization: Bearer <token>` dari [TokenStore] ke tiap
/// request (kecuali yang ditandai `skipAuth`).
class AuthInterceptor extends Interceptor {
  AuthInterceptor(this._tokenStore);

  final TokenStore _tokenStore;

  @override
  void onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) {
    final skip = options.extra['skipAuth'] == true;
    final token = _tokenStore.accessToken;
    if (!skip && token != null && token.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }
}
