// Unit test formatter — currency + date.

import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'package:emas_berlian_insight/utils/formatters/currency_formatter.dart';
import 'package:emas_berlian_insight/utils/formatters/date_formatter.dart';

void main() {
  setUpAll(() async {
    await initializeDateFormatting('id_ID');
  });

  group('CurrencyFormatter.rupiah', () {
    test('titik ribuan', () {
      expect(CurrencyFormatter.rupiah(5000000), 'Rp 5.000.000');
      expect(CurrencyFormatter.rupiah(1500), 'Rp 1.500');
    });
  });

  group('CurrencyFormatter.compact', () {
    test('jutaan → jt', () {
      final r = CurrencyFormatter.compact(828800000);
      expect(r.currency, 'Rp');
      expect(r.number, '828,8');
      expect(r.unit, 'jt');
    });

    test('miliaran → M', () {
      final r = CurrencyFormatter.compact(1510000000);
      expect(r.number, '1,5');
      expect(r.unit, 'M');
    });

    test('bulat tanpa desimal', () {
      final r = CurrencyFormatter.compact(2000000);
      expect(r.number, '2');
      expect(r.unit, 'jt');
    });
  });

  group('DateFormatter', () {
    test('long format id', () {
      expect(DateFormatter.long(DateTime(2026, 5, 17)), '17 Mei 2026');
    });

    test('short format', () {
      expect(DateFormatter.short(DateTime(2026, 5, 17)), '17/05/2026');
    });

    test('relative menit', () {
      final now = DateTime(2026, 5, 17, 14, 30);
      final dt = now.subtract(const Duration(minutes: 14));
      expect(DateFormatter.relative(dt, now: now), '14 menit lalu');
    });

    test('relative kemarin', () {
      final now = DateTime(2026, 5, 17, 14, 30);
      final dt = now.subtract(const Duration(days: 1));
      expect(DateFormatter.relative(dt, now: now), 'kemarin');
    });
  });
}
