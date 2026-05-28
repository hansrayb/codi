// Widget test Dashboard — repository di-override dengan fake (tanpa HTTP).
//
// Catatan: SummaryCard punya animasi blink infinite — JANGAN pumpAndSettle.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'package:emas_berlian_insight/theme/app_theme.dart';
import 'package:emas_berlian_insight/api/repositories/dashboard_repository.dart';
import 'package:emas_berlian_insight/features/dashboard/domain/dashboard_state.dart';
import 'package:emas_berlian_insight/features/dashboard/presentation/dashboard_screen.dart';
import 'package:emas_berlian_insight/features/dashboard/presentation/widgets/summary_card.dart';
import 'package:emas_berlian_insight/features/dashboard/presentation/widgets/stats_row.dart';
import 'package:emas_berlian_insight/models/dashboard_summary.dart';
import 'package:emas_berlian_insight/providers/token_store.dart';

import '../../helpers/fake_token_store.dart';

DashboardSummary _fixture() => DashboardSummary(
      periodLabel: 'MEI 2026',
      omzet: 828800000,
      trendText: '+321% MoM',
      trendDirection: TrendDirection.up,
      periodInfo: '17 hari · 55 order',
      sparkline: const [10, 20, 30, 46],
      stats: const [
        QuickStat(
          label: 'Order',
          value: '55',
          unit: 'tx',
          deltaText: '15 retail',
          direction: TrendDirection.up,
        ),
      ],
      aiSummary: AiSummary(
        paragraphs: const ['Kondisi sehat.'],
        updatedAt: DateTime(2026, 5, 17, 9, 14),
        dataPoints: 12,
      ),
      chart: const [ChartBar(label: '17', retail: 90, rotasi: 36)],
      highlights: [
        Highlight(
          title: 'Penjualan retail aktif',
          description: 'Rp 656 jt.',
          timestamp: DateTime(2026, 5, 14, 14, 30),
          severity: HighlightSeverity.green,
        ),
      ],
      updatedAt: DateTime(2026, 5, 17, 9, 28),
    );

class _FakeDashboardRepo implements DashboardRepository {
  @override
  Future<DashboardSummary> getSummary(Period period) async => _fixture();
}

Future<void> _pump(WidgetTester tester) {
  return tester.pumpWidget(
    ProviderScope(
      overrides: [
        dashboardRepositoryProvider.overrideWithValue(_FakeDashboardRepo()),
        tokenStoreProvider.overrideWithValue(FakeTokenStore()),
      ],
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

  testWidgets('success → render greeting + summary + stats',
      (tester) async {
    await _pump(tester);
    await tester.pump(); // loading
    await tester.pump(); // future resolves
    await tester.pump(const Duration(milliseconds: 16));

    expect(find.text('Bapak Leo Sastra C.W.'), findsOneWidget);
    expect(find.textContaining('OMZET MEI 2026'), findsOneWidget);
    expect(find.byType(SummaryCard), findsOneWidget);
    expect(find.byType(StatsRow), findsOneWidget);
    expect(find.text('Sorotan'), findsOneWidget);
  });
}
