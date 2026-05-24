// Widget test Laporan (S5) — mock data via controller (delay 700ms).

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'package:emas_berlian_insight/theme/app_theme.dart';
import 'package:emas_berlian_insight/features/reports/presentation/reports_screen.dart';
import 'package:emas_berlian_insight/features/reports/presentation/widgets/report_card.dart';
import 'package:emas_berlian_insight/features/reports/presentation/widgets/report_filter_bar.dart';
import 'package:emas_berlian_insight/features/shell/presentation/widgets/bottom_nav.dart';
import 'package:emas_berlian_insight/widgets/emas_loading.dart';

Future<void> _pump(WidgetTester tester) {
  return tester.pumpWidget(
    ProviderScope(
      child: MaterialApp(
        theme: AppTheme.darkTheme,
        home: const ReportsScreen(),
      ),
    ),
  );
}

Future<void> _settle(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 800));
  await tester.pump(const Duration(milliseconds: 16));
}

void main() {
  setUpAll(() async {
    await initializeDateFormatting('id_ID');
  });

  testWidgets('loading → skeleton shimmer', (tester) async {
    await _pump(tester);
    await tester.pump();

    expect(find.byType(EmasSkeleton), findsWidgets);

    await tester.pump(const Duration(milliseconds: 800));
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
    await tester.pump(const Duration(milliseconds: 800)); // reload
    await tester.pump(const Duration(milliseconds: 16));

    // Filter bulanIni → cuma grup Terbaru (3 card), Bulan Lalu hilang.
    expect(find.byType(ReportCard), findsNWidgets(3));
    expect(find.text('BULAN LALU'), findsNothing);
  });

  testWidgets('bottom nav active = Laporan', (tester) async {
    await _pump(tester);
    await _settle(tester);

    final nav = tester.widget<BottomNav>(find.byType(BottomNav));
    expect(nav.active, NavTab.laporan);
  });
}
