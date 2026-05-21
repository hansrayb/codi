import 'package:intl/intl.dart';

/// Format tanggal/waktu locale `id_ID` sesuai `docs/02-SPEC.md`.
abstract final class DateFormatter {
  const DateFormatter._();

  static final DateFormat _long = DateFormat('d MMMM yyyy', 'id_ID');
  static final DateFormat _short = DateFormat('dd/MM/yyyy', 'id_ID');
  static final DateFormat _dayMonthTime = DateFormat('d MMM HH:mm', 'id_ID');

  /// `17 Mei 2026`.
  static String long(DateTime dt) => _long.format(dt);

  /// `17/05/2026`.
  static String short(DateTime dt) => _short.format(dt);

  /// `17 mei 14:30` (lowercase, gaya timestamp highlight di mockup).
  static String dayMonthTime(DateTime dt) =>
      _dayMonthTime.format(dt).toLowerCase();

  /// Relatif singkat: `14 menit lalu`, `2 jam lalu`, `kemarin`.
  static String relative(DateTime dt, {DateTime? now}) {
    final ref = now ?? DateTime.now();
    final diff = ref.difference(dt);
    if (diff.inMinutes < 1) return 'baru saja';
    if (diff.inMinutes < 60) return '${diff.inMinutes} menit lalu';
    if (diff.inHours < 24) return '${diff.inHours} jam lalu';
    if (diff.inDays == 1) return 'kemarin';
    return '${diff.inDays} hari lalu';
  }
}
