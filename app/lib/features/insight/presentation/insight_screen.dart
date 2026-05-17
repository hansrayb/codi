import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/insight_detail.dart';
import '../../../theme/app_theme.dart';
import '../../../widgets/emas_error_view.dart';
import '../../../widgets/emas_loading.dart';
import '../../shell/presentation/widgets/bottom_nav.dart';
import '../application/insight_controller.dart';
import '../domain/insight_state.dart';
import 'widgets/composition_donut.dart';
import 'widgets/deep_analysis_card.dart';
import 'widgets/insight_hero.dart';
import 'widgets/kpi_grid.dart';

/// Insight (S4) — `docs/06-SCREENS.md`, layout match mockup
/// `docs/emas-berlian-insight.html` SCREEN 4.
///
/// Read-only premium: hero, KPI grid, donut komposisi, analisis Codi.
/// Pull-to-refresh, shimmer, error/offline. Bottom nav fungsional.
class InsightScreen extends ConsumerWidget {
  const InsightScreen({
    this.onBack,
    this.onOpenChat,
    this.onNavTap,
    this.showBottomNav = true,
    super.key,
  });

  /// Tap back / arrow hero — kembali ke Beranda.
  final VoidCallback? onBack;

  /// Tap FAB Codi / "Tanya Codi →" → Chat.
  final VoidCallback? onOpenChat;

  /// Tap item bottom nav lain (di-handle shell).
  final ValueChanged<NavTab>? onNavTap;

  /// Render BottomNav internal. AppShell set `false` — navbar di-host
  /// shell agar tak ikut animasi transisi tab.
  final bool showBottomNav;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(insightControllerProvider);

    return Scaffold(
      body: Stack(
        children: [
          SafeArea(
            bottom: false,
            child: switch (state) {
              InsightLoading() => const _LoadingView(),
              InsightError(:final message) => EmasErrorView(
                  message: message,
                  onRetry: () => ref
                      .read(insightControllerProvider.notifier)
                      .refresh(),
                ),
              InsightSuccess(:final data) => _Content(
                  onRefresh: () => ref
                      .read(insightControllerProvider.notifier)
                      .refresh(),
                  child: _InsightBody(
                    data: data,
                    onBack: onBack,
                    onOpenChat: onOpenChat,
                  ),
                ),
              InsightOffline(:final cached) => _Content(
                  isOffline: true,
                  onRefresh: () => ref
                      .read(insightControllerProvider.notifier)
                      .refresh(),
                  child: _InsightBody(
                    data: cached,
                    onBack: onBack,
                    onOpenChat: onOpenChat,
                  ),
                ),
            },
          ),
          if (showBottomNav)
            Positioned(
              left: 0,
              right: 0,
              bottom: 0,
              child: BottomNav(
                active: NavTab.insight,
                onTap: onNavTap,
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
        // Clearance nav floating (bar 64 + FAB rise 22 + margin 20) +
        // safe area sistem + napas.
        padding: EdgeInsets.only(
          bottom: 116 + MediaQuery.viewPaddingOf(context).bottom,
        ),
        children: [
          if (isOffline) const _OfflineBanner(),
          child,
        ],
      ),
    );
  }
}

class _InsightBody extends StatelessWidget {
  const _InsightBody({
    required this.data,
    this.onBack,
    this.onOpenChat,
  });

  final InsightDetail data;
  final VoidCallback? onBack;
  final VoidCallback? onOpenChat;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InsightHero(
          title: data.title,
          periodLabel: data.periodLabel,
          isLive: data.isLive,
          onBack: onBack,
        ),
        KpiGrid(kpis: data.kpis),
        CompositionDonut(
          totalLabel: data.donutTotalLabel,
          totalUnit: data.donutTotalUnit,
          caption: data.donutCaption,
          slices: data.donutSlices,
        ),
        DeepAnalysisCard(
          title: data.analysisTitle,
          author: data.analysisAuthor,
          updatedAt: data.analysisUpdatedAt,
          sections: data.analysisSections,
          meta: data.analysisMeta,
          onAskCodi: onOpenChat,
        ),
      ],
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
        EmasSkeleton(width: 200, height: 28),
        SizedBox(height: AppSpacing.s8),
        EmasSkeleton(width: 160, height: 14),
        SizedBox(height: AppSpacing.s24),
        Row(
          children: [
            Expanded(child: EmasSkeleton(width: 0, height: 80, radius: 14)),
            SizedBox(width: AppSpacing.s8),
            Expanded(child: EmasSkeleton(width: 0, height: 80, radius: 14)),
          ],
        ),
        SizedBox(height: AppSpacing.s8),
        Row(
          children: [
            Expanded(child: EmasSkeleton(width: 0, height: 80, radius: 14)),
            SizedBox(width: AppSpacing.s8),
            Expanded(child: EmasSkeleton(width: 0, height: 80, radius: 14)),
          ],
        ),
        SizedBox(height: AppSpacing.s16),
        EmasSkeleton(width: double.infinity, height: 132, radius: 16),
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
