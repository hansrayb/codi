import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../models/codi_session.dart';
import '../api_client.dart';
import '../api_exception.dart';

/// Akses endpoint profil/sesi — `GET /me/sessions`.
class ProfileRepository {
  ProfileRepository(this._dio);

  final Dio _dio;

  /// Daftar sesi orchestrator Codi aktif.
  Future<CodiSessions> getSessions() async {
    try {
      final res = await _dio.get<Map<String, dynamic>>('/me/sessions');
      return _map(res.data ?? const {});
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  CodiSessions _map(Map<String, dynamic> j) {
    final raw = j['sessions'];
    final list = raw is List ? raw : const <Object?>[];
    final sessions = [
      for (final s in list)
        if (s is Map<String, dynamic>) _session(s),
    ];
    final active = j['active'];
    return CodiSessions(
      active: active is int ? active : sessions.length,
      sessions: sessions,
    );
  }

  CodiSession _session(Map<String, dynamic> j) {
    return CodiSession(
      id: j['id']?.toString() ?? '',
      role: j['role']?.toString() ?? '',
      repoName: j['repo_name']?.toString() ??
          _basename(j['repo']?.toString() ?? ''),
      repo: j['repo']?.toString() ?? '',
      startedAt: _date(j['started_at']),
      lastActivityAt: _date(j['last_activity_at']),
      idleSeconds: j['idle_seconds'] is int ? j['idle_seconds'] as int : null,
    );
  }

  static DateTime? _date(Object? v) {
    if (v == null) return null;
    return DateTime.tryParse(v.toString())?.toLocal();
  }

  static String _basename(String path) {
    if (path.isEmpty) return '';
    final parts = path.split('/').where((p) => p.isNotEmpty);
    return parts.isEmpty ? path : parts.last;
  }
}

/// Provider repository profil.
final profileRepositoryProvider = Provider<ProfileRepository>((ref) {
  return ProfileRepository(ref.read(dioProvider));
});
