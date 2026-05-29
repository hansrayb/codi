import 'package:dio/dio.dart';

/// Jenis error API, dipetakan dari [DioException] ke pesan ramah
/// (`docs/02-SPEC.md` → Error Handling). Tidak menampilkan stack trace.
enum ApiErrorKind {
  timeout,
  noInternet,
  unauthorized,
  server,
  client,
  unknown,
}

/// Exception terstruktur untuk layer API.
class ApiException implements Exception {
  const ApiException({
    required this.kind,
    required this.message,
    this.statusCode,
  });

  /// Bangun dari [DioException].
  factory ApiException.fromDio(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return const ApiException(
          kind: ApiErrorKind.timeout,
          message: 'Sambungan lambat. Coba lagi sebentar.',
        );
      case DioExceptionType.connectionError:
        return const ApiException(
          kind: ApiErrorKind.noInternet,
          message: 'Tidak ada koneksi internet. Cek WiFi/data kamu.',
        );
      case DioExceptionType.badResponse:
        return _fromStatus(e.response?.statusCode, e.response?.data);
      case DioExceptionType.cancel:
        return const ApiException(
          kind: ApiErrorKind.unknown,
          message: 'Permintaan dibatalkan.',
        );
      case DioExceptionType.badCertificate:
      case DioExceptionType.unknown:
        return const ApiException(
          kind: ApiErrorKind.unknown,
          message: 'Terjadi kesalahan. Coba lagi nanti.',
        );
    }
  }

  final ApiErrorKind kind;

  /// Pesan ramah Bahasa Indonesia untuk ditampilkan ke user.
  final String message;

  final int? statusCode;

  /// True jika sesi habis / token invalid → app harus logout.
  bool get isUnauthorized => kind == ApiErrorKind.unauthorized;

  static ApiException _fromStatus(int? status, Object? data) {
    final code = status ?? 0;
    if (code == 401) {
      return const ApiException(
        kind: ApiErrorKind.unauthorized,
        message: 'Sesi habis, silakan login ulang.',
        statusCode: 401,
      );
    }
    if (code >= 500) {
      return ApiException(
        kind: ApiErrorKind.server,
        message: 'Layanan sedang tidak tersedia. Tim teknis sudah diberitahu.',
        statusCode: code,
      );
    }
    // 4xx lain — pakai message dari API kalau aman.
    final apiMsg = _extractMessage(data);
    return ApiException(
      kind: ApiErrorKind.client,
      message: apiMsg ?? 'Permintaan tidak dapat diproses.',
      statusCode: code,
    );
  }

  static String? _extractMessage(Object? data) {
    if (data is Map && data['error'] is Map) {
      final msg = (data['error'] as Map)['message'];
      if (msg is String && msg.isNotEmpty) return msg;
    }
    return null;
  }

  @override
  String toString() => 'ApiException($kind, $statusCode): $message';
}
