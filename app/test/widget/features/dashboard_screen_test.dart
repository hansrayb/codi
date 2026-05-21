// Widget test Dashboard — mock data via controller (delay 700ms).
//
// Catatan: SummaryCard punya animasi blink infinite (live dot), jadi
// JANGAN pakai pumpAndSettle (tak pernah settle). Pakai pump terukur.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'package:emas_berlian_insight/theme/app_theme.dart';
import 'package:emas_berlian_insight/features/dashboard/presentation/dashboard_screen.dart';
import 'package:emas_berlian_insight/features/dashboard/presentation/widgets/summary_card.dart';
import 'package:emas_berlian_insight/features/dashboard/presentation/widgets/stats_row.dart';
import 'package:emas_berlian_insight/widgets/emas_loading.dart';

Future<void> _pump(WidgetTester tester) {
  return tester.pumpWidget(
    ProviderScope(
      child: MaterialApp(
        theme: AppTheme.darkTheme,
        home: const DashboardScreen(),
      ),
    ),
  );
}

void main() {
  setUpAll(() async {
    await initializeDateFormatting('id_ID');
  });

  testWidgets('loading → skeleton shimmer', (tester) async {
    await _pump(tester);
    await tester.pump(); // build, masih loading

    expect(find.byType(EmasSkeleton), findsWidgets);

    // Tuntaskan timer mock (700ms) → success state. Tanpa pumpAndSettle
    // (blink animation infinite). Pump beberapa frame manual.
    await tester.pump(const Duration(milliseconds: 800));
    await tester.pump(const Duration(milliseconds: 16));
  });

  testWidgets('success → render greeting + summary + stats',
      (tester) async {
    await _pump(tester);
    await tester.pump(); // loading
    await tester.pump(const Duration(milliseconds: 800)); // mock delay
    await tester.pump(const Duration(milliseconds: 16)); // 1 frame

    expect(find.text('Bapak Leo Sastra C.W.'), findsOneWidget);
    expect(find.textContaining('OMZET MEI 2026'), findsOneWidget);
    expect(find.byType(SummaryCard), findsOneWidget);
    expect(find.byType(StatsRow), findsOneWidget);
    expect(find.text('Sorotan'), findsOneWidget);
  });
}
