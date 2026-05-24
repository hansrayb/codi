// Widget test Insight (S4) — mock data via controller (delay 700ms).
//
// Donut & KPI statis (tak ada animasi infinite), tapi tetap pakai pump
// terukur (konsisten dgn dashboard_screen_test) — bukan pumpAndSettle.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'package:emas_berlian_insight/theme/app_theme.dart';
import 'package:emas_berlian_insight/api/repositories/insight_repository.dart';
import 'package:emas_berlian_insight/features/dashboard/domain/dashboard_state.dart';
import 'package:emas_berlian_insight/features/insight/presentation/insight_screen.dart';
import 'package:emas_berlian_insight/features/insight/presentation/widgets/composition_donut.dart';
import 'package:emas_berlian_insight/features/insight/presentation/widgets/kpi_grid.dart';
import 'package:emas_berlian_insight/features/insight/presentation/widgets/insight_hero.dart';
import 'package:emas_berlian_insight/features/insight/presentation/widgets/deep_analysis_card.dart';
import 'package:emas_berlian_insight/features/shell/presentation/widgets/bottom_nav.dart';
import 'package:emas_berlian_insight/models/insight_detail.dart';

InsightDetail _fixture() => InsightDetail(
      title: 'Insight Operasional',
      periodLabel: 'Periode: 1 – 17 Mei 2026',
      isLive: true,
      kpis: const [
        InsightKpi(
          label: 'Omzet Total',
          value: 'Rp 828,8',
          unit: 'jt',
          deltaText: '+321% MoM',
          direction: TrendDirection.up,
        ),
        InsightKpi(
          label: 'Potensi Hilang',
          value: 'Rp 127',
          unit: 'jt',
          deltaText: '24 order expired',
          direction: TrendDirection.down,
          isCost: true,
        ),
      ],
      donutTotalLabel: '828,8',
      donutTotalUnit: 'jt',
      donutSlices: const [
        DonutSlice(label: 'Penjualan Emas', percent: 79.2, color: DonutColor.gold),
        DonutSlice(label: 'Rotasi Masuk', percent: 20.8, color: DonutColor.navy),
      ],
      donutCaption: 'Komposisi Omzet',
      analysisTitle: 'Analisis Mendalam',
      analysisAuthor: 'Disusun oleh Codi',
      analysisUpdatedAt: DateTime(2026, 5, 17, 9, 14),
      analysisSections: const [
        DeepAnalysisSection(heading: 'Yang Sehat', body: 'Omzet naik.'),
      ],
      analysisMeta: '12 data point · 4 sumber',
      updatedAt: DateTime(2026, 5, 17, 9, 28),
    );

class _FakeInsightRepo implements InsightRepository {
  @override
  Future<InsightDetail> getInsight(Period period) async => _fixture();
}

Future<void> _pump(
  WidgetTester tester, {
  VoidCallback? onBack,
  VoidCallback? onChat,
  ValueChanged<NavTab>? onNav,
}) {
  return tester.pumpWidget(
    ProviderScope(
      overrides: [
        insightRepositoryProvider.overrideWithValue(_FakeInsightRepo()),
      ],
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
