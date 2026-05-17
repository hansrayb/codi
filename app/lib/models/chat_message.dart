import 'package:flutter/foundation.dart';

/// Pengirim pesan.
enum MessageSender { user, bot }

/// Tren nilai di baris rich card (warna).
enum RichTrend { up, down, neutral }

/// Severity badge rich card.
enum RichBadgeColor { green, red, gold }

/// Satu baris data di rich card (label + value + trend).
@immutable
class RichRow {
  const RichRow({
    required this.label,
    required this.value,
    this.trend = RichTrend.neutral,
  });

  final String label;
  final String value;
  final RichTrend trend;
}

/// Tombol aksi rich card.
@immutable
class RichAction {
  const RichAction({
    required this.label,
    this.primary = true,
  });

  final String label;

  /// Primary = gold; false = secondary outline.
  final bool primary;
}

/// Card kaya di dalam pesan bot (`docs/06-SCREENS.md` → Rich Card).
@immutable
class RichCard {
  const RichCard({
    required this.title,
    this.badge,
    this.badgeColor = RichBadgeColor.green,
    this.rows = const [],
    this.sparkline = const [],
    this.actions = const [],
  });

  final String title;

  /// Label badge (mis. "SEHAT"). Null = tanpa badge.
  final String? badge;
  final RichBadgeColor badgeColor;
  final List<RichRow> rows;

  /// Titik inline chart (kosong = tanpa chart).
  final List<double> sparkline;
  final List<RichAction> actions;
}

/// Satu pesan chat.
@immutable
class ChatMessage {
  const ChatMessage({
    required this.id,
    required this.sender,
    required this.text,
    required this.time,
    this.responSeconds,
    this.card,
  });

  final String id;
  final MessageSender sender;
  final String text;
  final DateTime time;

  /// Durasi respon bot (detik) — tampil di msg-time bot.
  final double? responSeconds;

  /// Rich card opsional (hanya bot).
  final RichCard? card;

  bool get isUser => sender == MessageSender.user;
}
