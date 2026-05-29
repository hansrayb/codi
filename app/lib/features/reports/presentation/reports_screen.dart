import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/report_item.dart';
import '../../../theme/app_theme.dart';
import '../../../widgets/emas_error_view.dart';
import '../../../widgets/emas_loading.dart';
import '../../shell/presentation/widgets/bottom_nav.dart';
import '../application/reports_controller.dart';
import '../domain/reports_state.dart';
import 'widgets/report_card.dart';
import 'widgets/report_detail_sheet.dart';
import 'widgets/report_filter_bar.dart';

/// Laporan (S5) — `docs/06-SCREENS.md`, layout match mockup
/// `docs/emas-berlian-insight.html` SCREEN 5.
///
/// List laporan tergenerate + filter periode. Read-only eksekutif.
/// Pull-to-refresh, shimmer, error/offline. Bottom nav di-host shell.
class ReportsScreen extends ConsumerWidget {
  const ReportsScreen({
    this.onOpenChat,
    this.onNavTap,
    this.showBottomNav = true,
    super.key,
  });

  /// Tap FAB Codi → Chat.
  final VoidCallback? onOpenChat;

  /// Tap item bottom nav lain (di-handle shell).
  final ValueChanged<NavTab>? onNavTap;

  /// Render BottomNav internal. AppShell set `false`.
  final bool showBottomNav;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(reportsControllerProvider);

    return Scaffold(
      body: Stack(
        children: [
          SafeArea(
            bottom: false,
            child: switch (state) {
              ReportsLoading() => const _LoadingView(),
              ReportsError(:final message) => EmasErrorView(
                  message: message,
                  onRetry: () => ref
                      .read(reportsControllerProvider.notifier)
                      .refresh(),
                ),
              ReportsSuccess(:final groups) => _Content(
                  onRefresh: () => ref
                      .read(reportsControllerProvider.notifier)
                      .refresh(),
                  child: _ReportsBody(groups: groups),
                ),
              ReportsOffline(:final cached) => _Content(
                  isOffline: true,
                  onRefresh: () => ref
                      .read(reportsControllerProvider.notifier)
                      .refresh(),
                  child: _ReportsBody(groups: cached),
                ),
            },
          ),
          if (showBottomNav)
            Positioned(
              left: 0,
              right: 0,
              bottom: 0,
              child: BottomNav(
                active: NavTab.laporan,
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

class _ReportsBody extends StatelessWidget {
  const _ReportsBody({required this.groups});

  final List<ReportGroup> groups;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Consumer(
      builder: (context, ref, _) {
        final filter = ref.watch(selectedReportFilterProvider);
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.s20,
                AppSpacing.s14,
                AppSpacing.s20,
                AppSpacing.s16,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Laporan',
                    style: AppTypography.headlineL.copyWith(
                      color: c.ink,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.s4),
                  Text(
                    'Dokumen operasional tergenerate oleh Codi',
                    style: AppTypography.bodyS.copyWith(color: c.inkMuted),
                  ),
                ],
              ),
            ),
            ReportFilterBar(
              selected: filter,
              onChanged: (f) => ref
                  .read(selectedReportFilterProvider.notifier)
                  .state = f,
            ),
            const SizedBox(height: AppSpacing.s8),
            for (final g in groups) ...[
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.s20,
                  AppSpacing.s12,
                  AppSpacing.s20,
                  AppSpacing.s8,
                ),
                child: Text(
                  g.label.toUpperCase(),
                  style: AppTypography.labelS.copyWith(
                    color: c.inkMuted,
                    fontSize: 10,
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.s20,
                ),
                child: Column(
                  children: [
                    for (var i = 0; i < g.items.length; i++) ...[
                      if (i > 0) const SizedBox(height: AppSpacing.s10),
                      ReportCard(
                        item: g.items[i],
                        onTap: g.items[i].detailRef == null
                            ? null
                            : () => ReportDetailSheet.open(
                                  context,
                                  g.items[i],
                                ),
                      ),
                    ],
                  ],
                ),
              ),
            ],
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
        EmasSkeleton(width: 140, height: 28),
        SizedBox(height: AppSpacing.s8),
        EmasSkeleton(width: 220, height: 14),
        SizedBox(height: AppSpacing.s20),
        EmasSkeleton(width: double.infinity, height: 34, radius: 999),
        SizedBox(height: AppSpacing.s20),
        EmasLoadingCard(),
        SizedBox(height: AppSpacing.s10),
        EmasLoadingCard(),
        SizedBox(height: AppSpacing.s10),
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
