import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../api/repositories/reports_repository.dart';
import '../../../../models/report_detail.dart';
import '../../../../models/report_item.dart';
import '../../../../theme/app_theme.dart';

/// Bottom sheet drill-down detail laporan (S5).
///
/// Header (ikon kategori + judul + badge status) tampil instan dari [item];
/// blok summary + rows di-fetch `GET /reports/detail?ref=`.
class ReportDetailSheet extends ConsumerWidget {
  const ReportDetailSheet({required this.item, super.key});

  final ReportItem item;

  /// Buka sheet. No-op kalau item tak punya `detailRef`.
  static Future<void> open(BuildContext context, ReportItem item) {
    if (item.detailRef == null) return Future<void>.value();
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => ReportDetailSheet(item: item),
    );
  }

  ({Color fg, Color bg, Color border, IconData icon}) _style(
    BuildContext context,
  ) {
    final c = context.colors;
    switch (item.category) {
      case ReportCategory.omzet:
        return (
          fg: c.gold,
          bg: c.goldSoft,
          border: c.goldLine,
          icon: Icons.show_chart,
        );
      case ReportCategory.payroll:
        return (
          fg: c.navyBlue,
          bg: c.navySoft,
          border: c.navyBlue.withValues(alpha: 0.3),
          icon: Icons.description_outlined,
        );
      case ReportCategory.absensi:
        return (
          fg: c.green,
          bg: c.greenSoft,
          border: c.green.withValues(alpha: 0.3),
          icon: Icons.fact_check_outlined,
        );
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final s = _style(context);
    final maxH = MediaQuery.sizeOf(context).height * 0.85;

    return SafeArea(
      child: Container(
        constraints: BoxConstraints(maxHeight: maxH),
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.s20,
          AppSpacing.s12,
          AppSpacing.s20,
          AppSpacing.s20,
        ),
        decoration: BoxDecoration(
          color: c.bgApp,
          borderRadius: const BorderRadius.vertical(
            top: Radius.circular(AppRadius.r20),
          ),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _Handle(color: c.line),
            const SizedBox(height: AppSpacing.s12),
            Row(
              children: [
                Container(
                  width: 42,
                  height: 42,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: s.bg,
                    borderRadius: BorderRadius.circular(AppRadius.r12),
                    border: Border.all(color: s.border),
                  ),
                  child: Icon(s.icon, size: 20, color: s.fg),
                ),
                const SizedBox(width: AppSpacing.s14),
                Expanded(
                  child: Text(
                    item.title,
                    style: AppTypography.headlineS.copyWith(color: c.ink),
                  ),
                ),
                const SizedBox(width: AppSpacing.s8),
                _Badge(status: item.status),
              ],
            ),
            const SizedBox(height: AppSpacing.s16),
            Flexible(
              child: _DetailBody(ref: item.detailRef ?? ''),
            ),
          ],
        ),
      ),
    );
  }
}

/// Fetch + render summary/rows. Loading/error/empty state.
class _DetailBody extends ConsumerWidget {
  const _DetailBody({required this.ref});

  final String ref;

  @override
  Widget build(BuildContext context, WidgetRef wref) {
    final c = context.colors;
    final future = wref.watch(_reportDetailProvider(ref));
    return future.when(
      loading: () => const Padding(
        padding: EdgeInsets.symmetric(vertical: AppSpacing.s32),
        child: Center(child: CircularProgressIndicator()),
      ),
      error: (e, _) => Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.s24),
        child: Text(
          'Gagal memuat detail.\n$e',
          textAlign: TextAlign.center,
          style: AppTypography.bodyS.copyWith(color: c.red),
        ),
      ),
      data: (d) => SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (d.summary.isNotEmpty) _SummaryBlock(stats: d.summary),
            if (d.rows.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.s16),
              const _SectionLabel('Rincian'),
              const SizedBox(height: AppSpacing.s8),
              for (var i = 0; i < d.rows.length; i++) ...[
                if (i > 0) const SizedBox(height: AppSpacing.s8),
                _RowTile(row: d.rows[i]),
              ],
            ],
          ],
        ),
      ),
    );
  }
}

/// Provider future detail per `ref` (auto-dispose, cache selama sheet hidup).
final _reportDetailProvider =
    FutureProvider.autoDispose.family<ReportDetail, String>((ref, key) {
  return ref.read(reportsRepositoryProvider).getReportDetail(key);
});

class _SummaryBlock extends StatelessWidget {
  const _SummaryBlock({required this.stats});

  final List<ReportStat> stats;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Container(
      padding: const EdgeInsets.all(AppSpacing.s16),
      decoration: BoxDecoration(
        color: c.bgCard,
        borderRadius: BorderRadius.circular(AppRadius.r16),
        border: Border.all(color: c.line),
      ),
      child: Column(
        children: [
          for (var i = 0; i < stats.length; i++) ...[
            if (i > 0) const SizedBox(height: AppSpacing.s10),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  stats[i].label,
                  style: AppTypography.bodyS.copyWith(color: c.inkMuted),
                ),
                const SizedBox(width: AppSpacing.s12),
                Expanded(
                  child: Text(
                    stats[i].value,
                    textAlign: TextAlign.right,
                    style: AppTypography.bodyM.copyWith(
                      color: c.ink,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _RowTile extends StatelessWidget {
  const _RowTile({required this.row});

  final ReportDetailRow row;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                row.label,
                style: AppTypography.bodyM.copyWith(color: c.ink),
              ),
              if (row.sub.isNotEmpty) ...[
                const SizedBox(height: 1),
                Text(
                  row.sub,
                  style: AppTypography.bodyS
                      .copyWith(color: c.inkMuted, fontSize: 11),
                ),
              ],
            ],
          ),
        ),
        const SizedBox(width: AppSpacing.s12),
        Text(
          row.value,
          style: AppTypography.bodyM.copyWith(
            color: c.ink,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text);
  final String text;
  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Text(
      text.toUpperCase(),
      style: AppTypography.labelS.copyWith(
        color: c.inkFaint,
        letterSpacing: 1.2,
        fontWeight: FontWeight.w700,
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  const _Badge({required this.status});

  final ReportStatus status;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final isFinal = status == ReportStatus.finalized;
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.s8,
        vertical: AppSpacing.s2 + 1,
      ),
      decoration: BoxDecoration(
        color: isFinal ? c.greenSoft : c.amberSoft,
        borderRadius: BorderRadius.circular(AppRadius.r4 + 2),
      ),
      child: Text(
        status.label.toUpperCase(),
        style: AppTypography.labelS.copyWith(
          color: isFinal ? c.green : c.amber,
          fontSize: 9,
          letterSpacing: 0.8,
        ),
      ),
    );
  }
}

class _Handle extends StatelessWidget {
  const _Handle({required this.color});
  final Color color;
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Container(
        width: 36,
        height: 4,
        decoration: BoxDecoration(
          color: color,
          borderRadius: BorderRadius.circular(2),
        ),
      ),
    );
  }
}
