import 'package:intl/intl.dart';

/// Format mata uang IDR sesuai `docs/02-SPEC.md` & mockup
/// `docs/emas-berlian-insight.html`.
abstract final class CurrencyFormatter {
  const CurrencyFormatter._();

  static final NumberFormat _full = NumberFormat.decimalPattern('id_ID');

  /// Format penuh dengan titik ribuan: `Rp 5.000.000`.
  static String rupiah(num value) {
    return 'Rp ${_full.format(value)}';
  }

  /// Format ringkas hero: nilai besar → `828,8 jt` / `1,51 M`.
  /// Mengembalikan `(currency, number, unit)` agar bisa di-style berbeda
  /// (currency & unit lebih kecil di summary card).
  static ({String currency, String number, String unit}) compact(num value) {
    final abs = value.abs();
    if (abs >= 1000000000) {
      return (
        currency: 'Rp',
        number: _trim(value / 1000000000),
        unit: 'M',
      );
    }
    if (abs >= 1000000) {
      return (
        currency: 'Rp',
        number: _trim(value / 1000000),
        unit: 'jt',
      );
    }
    if (abs >= 1000) {
      return (
        currency: 'Rp',
        number: _trim(value / 1000),
        unit: 'rb',
      );
    }
    return (currency: 'Rp', number: _full.format(value), unit: '');
  }

  /// 1 desimal, koma sebagai pemisah (locale id): `828.8` → `828,8`.
  static String _trim(double v) {
    final s = v.toStringAsFixed(1);
    return s.endsWith('.0')
        ? s.substring(0, s.length - 2)
        : s.replaceAll('.', ',');
  }
}
