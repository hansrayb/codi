// Widget test Insight (S4) — mock data via controller (delay 700ms).
//
// Donut & KPI statis (tak ada animasi infinite), tapi tetap pakai pump
// terukur (konsisten dgn dashboard_screen_test) — bukan pumpAndSettle.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'package:emas_berlian_insight/theme/app_theme.dart';
import 'package:emas_berlian_insight/features/insight/presentation/insight_screen.dart';
import 'package:emas_berlian_insight/features/insight/presentation/widgets/composition_donut.dart';
import 'package:emas_berlian_insight/features/insight/presentation/widgets/kpi_grid.dart';
import 'package:emas_berlian_insight/features/insight/presentation/widgets/insight_hero.dart';
import 'package:emas_berlian_insight/features/insight/presentation/widgets/deep_analysis_card.dart';
import 'package:emas_berlian_insight/features/shell/presentation/widgets/bottom_nav.dart';
import 'package:emas_berlian_insight/widgets/emas_loading.dart';

Future<void> _pump(
  WidgetTester tester, {
  VoidCallback? onBack,
  VoidCallback? onChat,
  ValueChanged<NavTab>? onNav,
}) {
  return tester.pumpWidget(
    ProviderScope(
      child: MaterialApp(
        theme: AppTheme.darkTheme,
        home: InsightScreen(
          onBack: onBack,
          onOpenChat: onChat,
          onNavTap: onNav,
        ),
      ),
    ),
  );
}

Future<void> _settleMock(WidgetTester tester) async {
  await tester.pump(); // build, loading
  await tester.pump(const Duration(milliseconds: 800)); // mock delay
  await tester.pump(const Duration(milliseconds: 16)); // 1 frame
}

void main() {
  setUpAll(() async {
    await initializeDateFormatting('id_ID');
  });

  testWidgets('loading → skeleton shimmer', (tester) async {
    await _pump(tester);
    await tester.pump(); // masih loading

    expect(find.byType(EmasSkeleton), findsWidgets);

    await tester.pump(const Duration(milliseconds: 800));
    await tester.pump(const Duration(milliseconds: 16));
  });

  testWidgets('success → render hero + KPI + donut + analisis',
      (tester) async {
    await _pump(tester);
    await _settleMock(tester);

    expect(find.text('Insight Operasional'), findsOneWidget);
    // periodLabel di RichText (split TextSpan) — assert via widget prop.
    final hero = tester.widget<InsightHero>(find.byType(InsightHero));
    expect(hero.periodLabel, 'Periode: 1 – 17 Mei 2026');
    expect(hero.isLive, isTrue);
    expect(find.text('OMZET TOTAL'), findsOneWidget);
    expect(find.text('POTENSI HILANG'), findsOneWidget);
    expect(find.byType(KpiGrid), findsOneWidget);
    expect(find.byType(CompositionDonut), findsOneWidget);
    expect(find.textContaining('KOMPOSISI OMZET'), findsOneWidget);
    expect(find.byType(DeepAnalysisCard), findsOneWidget);
    expect(find.textContaining('Analisis Mendalam'), findsOneWidget);
  });

  testWidgets('tap back arrow → onBack dipanggil', (tester) async {
    var backed = false;
    await _pump(tester, onBack: () => backed = true);
    await _settleMock(tester);

    await tester.tap(find.byIcon(Icons.arrow_back));
    await tester.pump();

    expect(backed, isTrue);
  });

  testWidgets('tap "Tanya Codi →" → onOpenChat dipanggil', (tester) async {
    var chatted = false;
    await _pump(tester, onChat: () => chatted = true);
    await _settleMock(tester);

    // Card analisis di bawah fold viewport test → scroll dulu.
    await tester.ensureVisible(find.text('Tanya Codi →'));
    await tester.pump();
    await tester.tap(find.text('Tanya Codi →'));
    await tester.pump();

    expect(chatted, isTrue);
  });

  testWidgets('bottom nav active = Insight', (tester) async {
    await _pump(tester);
    await _settleMock(tester);

    final nav = tester.widget<BottomNav>(find.byType(BottomNav));
    expect(nav.active, NavTab.insight);
  });
}
