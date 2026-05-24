// Widget test AppShell — navigasi 4 tab fungsional.
//
// Dashboard punya blink anim infinite (live dot) → JANGAN pumpAndSettle.
// Pump terukur. Tab transition (_TabLayer) 200ms.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'package:emas_berlian_insight/api/repositories/dashboard_repository.dart';
import 'package:emas_berlian_insight/api/repositories/insight_repository.dart';
import 'package:emas_berlian_insight/features/dashboard/domain/dashboard_state.dart';
import 'package:emas_berlian_insight/models/dashboard_summary.dart';
import 'package:emas_berlian_insight/models/insight_detail.dart';
import 'package:emas_berlian_insight/features/shell/presentation/app_shell.dart';
import 'package:emas_berlian_insight/features/shell/presentation/widgets/bottom_nav.dart';
import 'package:emas_berlian_insight/features/dashboard/presentation/dashboard_screen.dart';
import 'package:emas_berlian_insight/features/insight/presentation/insight_screen.dart';
import 'package:emas_berlian_insight/features/reports/presentation/reports_screen.dart';
import 'package:emas_berlian_insight/features/profile/presentation/profile_screen.dart';

class _FakeDashboardRepo implements DashboardRepository {
  @override
  Future<DashboardSummary> getSummary(Period period) async => DashboardSummary(
        periodLabel: 'MEI 2026',
        omzet: 828800000,
        trendText: '+321% MoM',
        trendDirection: TrendDirection.up,
        periodInfo: '17 hari',
        sparkline: const [10, 46],
        stats: const [],
        aiSummary: AiSummary(
          paragraphs: const ['Sehat.'],
          updatedAt: DateTime(2026, 5, 17),
          dataPoints: 12,
        ),
        chart: const [ChartBar(label: '17', retail: 90, rotasi: 36)],
        highlights: const [],
        updatedAt: DateTime(2026, 5, 17),
      );
}

class _FakeInsightRepo implements InsightRepository {
  @override
  Future<InsightDetail> getInsight(Period period) async => InsightDetail(
        title: 'Insight Operasional',
        periodLabel: 'Periode: 1 – 17 Mei 2026',
        isLive: true,
        kpis: const [],
        donutTotalLabel: '828,8',
        donutTotalUnit: 'jt',
        donutSlices: const [],
        donutCaption: 'Komposisi Omzet',
        analysisTitle: 'Analisis Mendalam',
        analysisAuthor: 'Codi',
        analysisUpdatedAt: DateTime(2026, 5, 17),
        analysisSections: const [],
        analysisMeta: '12 data point',
        updatedAt: DateTime(2026, 5, 17),
      );
}

Future<void> _pump(WidgetTester tester) {
  return tester.pumpWidget(
    ProviderScope(
      overrides: [
        dashboardRepositoryProvider.overrideWithValue(_FakeDashboardRepo()),
        insightRepositoryProvider.overrideWithValue(_FakeInsightRepo()),
      ],
      child: const MaterialApp(home: AppShell()),
    ),
  );
}

// Mock delay (700ms) + transition (200ms) + napas.
Future<void> _settle(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 800));
  await tester.pump(const Duration(milliseconds: 300));
}

Future<void> _tapNav(WidgetTester tester, String label) async {
  // Label nav bisa sama dgn judul screen (mis. "Laporan") → tap
  // spesifik item di dalam BottomNav.
  await tester.tap(
    find.descendant(
      of: find.byType(BottomNav),
      matching: find.text(label),
    ),
  );
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 300)); // transition
  await tester.pump(const Duration(milliseconds: 800)); // mock delay
}

void main() {
  setUpAll(() async {
    await initializeDateFormatting('id_ID');
  });

  testWidgets('default tab = Beranda (Dashboard)', (tester) async {
    await _pump(tester);
    await _settle(tester);

    expect(find.byType(DashboardScreen), findsOneWidget);
    final nav = tester.widget<BottomNav>(find.byType(BottomNav).first);
    expect(nav.active, NavTab.beranda);
  });

  testWidgets('tap nav Insight → InsightScreen + active sync',
      (tester) async {
    await _pump(tester);
    await _settle(tester);

    await _tapNav(tester, 'Insight');

    expect(find.text('Insight Operasional'), findsOneWidget);
    final nav = tester.widget<BottomNav>(find.byType(BottomNav).first);
    expect(nav.active, NavTab.insight);
  });

  testWidgets('tap nav Laporan → ReportsScreen', (tester) async {
    await _pump(tester);
    await _settle(tester);

    await _tapNav(tester, 'Laporan');

    expect(find.byType(ReportsScreen), findsOneWidget);
    expect(
      find.text('Dokumen operasional tergenerate oleh Codi'),
      findsOneWidget,
    );
    final nav = tester.widget<BottomNav>(find.byType(BottomNav).first);
    expect(nav.active, NavTab.laporan);
  });

  testWidgets('tap nav Profil → ProfileScreen', (tester) async {
    await _pump(tester);
    await _settle(tester);

    await _tapNav(tester, 'Profil');

    expect(find.byType(ProfileScreen), findsOneWidget);
    expect(find.text('Leo Sastra C.W.'), findsOneWidget);
    final nav = tester.widget<BottomNav>(find.byType(BottomNav).first);
    expect(nav.active, NavTab.profil);
  });

  testWidgets('navbar di-host shell (1 BottomNav, bukan per-tab)',
      (tester) async {
    await _pump(tester);
    await _settle(tester);

    // Screen di-set showBottomNav:false → cuma 1 BottomNav (shell).
    expect(find.byType(BottomNav), findsOneWidget);
    expect(find.byType(InsightScreen), findsOneWidget); // tetap di tree
  });

  testWidgets('Insight → balik Beranda via nav', (tester) async {
    await _pump(tester);
    await _settle(tester);

    await _tapNav(tester, 'Insight');
    expect(find.text('Insight Operasional'), findsOneWidget);

    await _tapNav(tester, 'Beranda');
    final nav = tester.widget<BottomNav>(find.byType(BottomNav).first);
    expect(nav.active, NavTab.beranda);
  });
}
