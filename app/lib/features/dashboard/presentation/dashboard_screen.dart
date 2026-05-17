import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/dashboard_summary.dart';
import '../../../theme/app_theme.dart';
import '../../../widgets/emas_error_view.dart';
import '../../../widgets/emas_loading.dart';
import '../../shell/presentation/widgets/bottom_nav.dart';
import '../application/dashboard_controller.dart';
import '../domain/dashboard_state.dart';
import 'widgets/ai_summary_card.dart';
import 'widgets/chart_card.dart';
import 'widgets/greeting_header.dart';
import 'widgets/highlight_list.dart';
import 'widgets/period_selector.dart';
import 'widgets/stats_row.dart';
import 'widgets/summary_card.dart';

/// Dashboard (Beranda) — `docs/06-SCREENS.md` S2, layout match mockup
/// `docs/emas-berlian-insight.html`.
///
/// Pull-to-refresh, shimmer loading, error state. Bottom nav visual.
class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({
    this.onOpenChat,
    this.onOpenInsight,
    super.key,
  });

  /// Tap FAB Codi → Chat (di-wire saat Chat screen ada).
  final VoidCallback? onOpenChat;

  /// Tap AI summary → Insight (di-wire saat Insight screen ada).
  final VoidCallback? onOpenInsight;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(dashboardControllerProvider);

    return Scaffold(
      body: Stack(
        children: [
          SafeArea(
            bottom: false,
            child: switch (state) {
              DashboardLoading() => const _LoadingView(),
              DashboardError(:final message) => EmasErrorView(
                  message: message,
                  onRetry: () => ref
                      .read(dashboardControllerProvider.notifier)
                      .refresh(),
                ),
              DashboardSuccess(:final data) => _Content(
                  onRefresh: () => ref
                      .read(dashboardControllerProvider.notifier)
                      .refresh(),
                  child: _DashboardBody(
                    data: data,
                    onOpenInsight: onOpenInsight,
                  ),
                ),
              DashboardOffline(:final cached) => _Content(
                  isOffline: true,
                  onRefresh: () => ref
                      .read(dashboardControllerProvider.notifier)
                      .refresh(),
                  child: _DashboardBody(
                    data: cached,
                    onOpenInsight: onOpenInsight,
                  ),
                ),
            },
          ),
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: BottomNav(
              active: NavTab.beranda,
              onFabTap: onOpenChat,
            ),
          ),
        ],
      ),
    );
  }
}

class _Content extends StatelessWidget {
  const _Content({
    required this.onRefresh,
    required this.child,
    this.isOffline = false,
  });

  final Future<void> Function() onRefresh;
  final Widget child;
  final bool isOffline;

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: onRefresh,
      color: context.colors.gold,
      backgroundColor: context.colors.bgElev,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.only(bottom: 90),
        children: [
          if (isOffline) const _OfflineBanner(),
          child,
        ],
      ),
    );
  }
}

class _DashboardBody extends StatelessWidget {
  const _DashboardBody({required this.data, this.onOpenInsight});

  final DashboardSummary data;
  final VoidCallback? onOpenInsight;

  @override
  Widget build(BuildContext context) {
    return Consumer(
      builder: (context, ref, _) {
        final period = ref.watch(selectedPeriodProvider);
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const GreetingHeader(
              name: 'Leo Sastra C.W.',
              title: 'Direktur Utama',
            ),
            PeriodSelector(
              selected: period,
              onChanged: (p) =>
                  ref.read(selectedPeriodProvider.notifier).state = p,
            ),
            SummaryCard(data: data),
            StatsRow(stats: data.stats),
            AiSummaryCard(
              summary: data.aiSummary,
              onTap: onOpenInsight,
            ),
            ChartCard(bars: data.chart),
            HighlightList(highlights: data.highlights),
          ],
        );
      },
    );
  }
}

class _LoadingView extends StatelessWidget {
  const _LoadingView();

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.s20),
      children: const [
        SizedBox(height: AppSpacing.s12),
        EmasSkeleton(width: 180, height: 40),
        SizedBox(height: AppSpacing.s20),
        EmasSkeleton(width: double.infinity, height: 44, radius: 12),
        SizedBox(height: AppSpacing.s16),
        EmasSkeleton(width: double.infinity, height: 150, radius: 20),
        SizedBox(height: AppSpacing.s16),
        EmasLoadingCard(),
        SizedBox(height: AppSpacing.s16),
        EmasLoadingCard(),
      ],
    );
  }
}

class _OfflineBanner extends StatelessWidget {
  const _OfflineBanner();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: context.colors.amberSoft,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.s20,
        vertical: AppSpacing.s8,
      ),
      child: Text(
        'Menampilkan data terakhir karena offline',
        style: AppTypography.bodyS.copyWith(color: context.colors.amber),
      ),
    );
  }
}
