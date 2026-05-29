// Widget test Laporan (S5) — fake ReportsRepository via override.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'package:emas_berlian_insight/theme/app_theme.dart';
import 'package:emas_berlian_insight/api/repositories/reports_repository.dart';
import 'package:emas_berlian_insight/models/report_detail.dart';
import 'package:emas_berlian_insight/models/report_item.dart';
import 'package:emas_berlian_insight/features/reports/presentation/reports_screen.dart';
import 'package:emas_berlian_insight/features/reports/presentation/widgets/report_card.dart';
import 'package:emas_berlian_insight/features/reports/presentation/widgets/report_filter_bar.dart';
import 'package:emas_berlian_insight/features/shell/presentation/widgets/bottom_nav.dart';
import 'package:emas_berlian_insight/widgets/emas_loading.dart';

ReportItem _item(String title, ReportCategory cat, ReportStatus st) =>
    ReportItem(
      title: title,
      category: cat,
      status: st,
      createdAt: DateTime(2026, 5, 17),
      meta: '17 Mei 2026 · 4 hal',
      detailRef: 'payroll:6',
    );

/// Fake repo: `bulanIni` → cuma grup Terbaru (3 card), lainnya 5 card.
class _FakeReportsRepo implements ReportsRepository {
  @override
  Future<ReportDetail> getReportDetail(String ref) async {
    await Future<void>.delayed(const Duration(milliseconds: 10));
    return ReportDetail(
      ref: ref,
      title: 'Payroll Mei 2026',
      category: ReportCategory.payroll,
      status: ReportStatus.finalized,
      summary: const [
        ReportStat(label: 'Total Net', value: 'Rp 159.410.448'),
      ],
      rows: const [
        ReportDetailRow(
          label: 'Leo Sastra',
          sub: 'Pimpinan',
          value: 'Rp 27.909.901',
        ),
      ],
    );
  }

  @override
  Future<List<ReportGroup>> getReports(ReportFilter filter) async {
    // Delay kecil agar frame loading (skeleton) teramati di test.
    await Future<void>.delayed(const Duration(milliseconds: 50));
    final terbaru = ReportGroup(
      label: 'Terbaru',
      items: [
        _item('Ringkasan Omzet — Mei 2026', ReportCategory.omzet,
            ReportStatus.finalized),
        _item('Payroll Run — Mei 2026', ReportCategory.payroll,
            ReportStatus.draft),
        _item('Rekap Absensi — Mei 2026', ReportCategory.absensi,
            ReportStatus.finalized),
      ],
    );
    if (filter == ReportFilter.bulanIni) return [terbaru];
    final bulanLalu = ReportGroup(
      label: 'Bulan Lalu',
      items: [
        _item('Ringkasan Omzet — April 2026', ReportCategory.omzet,
            ReportStatus.finalized),
        _item('Payroll Run — April 2026', ReportCategory.payroll,
            ReportStatus.finalized),
      ],
    );
    return [terbaru, bulanLalu];
  }
}

Future<void> _pump(WidgetTester tester) {
  return tester.pumpWidget(
    ProviderScope(
      overrides: [
        reportsRepositoryProvider.overrideWithValue(_FakeReportsRepo()),
      ],
      child: MaterialApp(
        theme: AppTheme.darkTheme,
        home: const ReportsScreen(),
      ),
    ),
  );
}

Future<void> _settle(WidgetTester tester) async {
  await tester.pump(); // build, loading
  await tester.pump(const Duration(milliseconds: 100)); // fake repo delay
  await tester.pump(const Duration(milliseconds: 16)); // 1 frame
}

void main() {
  setUpAll(() async {
    await initializeDateFormatting('id_ID');
  });

  testWidgets('loading → skeleton shimmer', (tester) async {
    await _pump(tester);
    await tester.pump();

    expect(find.byType(EmasSkeleton), findsWidgets);

    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 16));
  });

  testWidgets('success → head + filter + report cards', (tester) async {
    await _pump(tester);
    await _settle(tester);

    expect(find.text('Laporan'), findsWidgets); // head + nav
    expect(
      find.text('Dokumen operasional tergenerate oleh Codi'),
      findsOneWidget,
    );
    expect(find.byType(ReportFilterBar), findsOneWidget);
    expect(find.byType(ReportCard), findsNWidgets(5)); // 3 + 2
    expect(find.text('Ringkasan Omzet — Mei 2026'), findsOneWidget);
    expect(find.text('TERBARU'), findsOneWidget);
    expect(find.text('BULAN LALU'), findsOneWidget);
  });

  testWidgets('tap filter Bulan Ini → grup menyempit', (tester) async {
    await _pump(tester);
    await _settle(tester);

    await tester.tap(find.text('Bulan Ini'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100)); // reload
    await tester.pump(const Duration(milliseconds: 16));

    // Filter bulanIni → cuma grup Terbaru (3 card), Bulan Lalu hilang.
    expect(find.byType(ReportCard), findsNWidgets(3));
    expect(find.text('BULAN LALU'), findsNothing);
  });

  testWidgets('tap card → detail sheet muncul (summary + row)',
      (tester) async {
    await _pump(tester);
    await _settle(tester);

    await tester.tap(find.text('Ringkasan Omzet — Mei 2026'));
    await tester.pump(); // open sheet → loading
    await tester.pump(const Duration(milliseconds: 50)); // fake detail delay
    await tester.pump(const Duration(milliseconds: 16));

    expect(find.text('Rp 159.410.448'), findsOneWidget);
    expect(find.text('Leo Sastra'), findsOneWidget);
    expect(find.text('Pimpinan'), findsOneWidget);
  });

  testWidgets('bottom nav active = Laporan', (tester) async {
    await _pump(tester);
    await _settle(tester);

    final nav = tester.widget<BottomNav>(find.byType(BottomNav));
    expect(nav.active, NavTab.laporan);
  });
}
