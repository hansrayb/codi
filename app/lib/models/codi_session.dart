import 'package:flutter/foundation.dart';

/// Satu sesi orchestrator Codi aktif — hasil `GET /me/sessions`.
@immutable
class CodiSession {
  const CodiSession({
    required this.id,
    required this.role,
    required this.repoName,
    this.repo = '',
    this.startedAt,
    this.lastActivityAt,
    this.idleSeconds,
  });

  final String id;
  final String role;

  /// Basename repo untuk display (mis. "lumbungemas-prod").
  final String repoName;

  /// Path penuh repo.
  final String repo;

  final DateTime? startedAt;
  final DateTime? lastActivityAt;

  /// Detik idle sejak aktivitas terakhir (null kalau tak tersedia).
  final int? idleSeconds;
}

/// Daftar sesi + jumlah aktif.
@immutable
class CodiSessions {
  const CodiSessions({required this.active, required this.sessions});

  final int active;
  final List<CodiSession> sessions;

  static const empty = CodiSessions(active: 0, sessions: []);
}
