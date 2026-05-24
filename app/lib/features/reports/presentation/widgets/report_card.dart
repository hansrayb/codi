import 'package:flutter/material.dart';

import '../../../../models/report_item.dart';
import '../../../../theme/app_theme.dart';

/// Kartu laporan (mockup `.report-card`).
///
/// Ikon kategori berwarna · judul + meta + badge status · chevron.
/// Tap → [onTap] (detail/export — di-wire saat backend siap).
class ReportCard extends StatelessWidget {
  const ReportCard({required this.item, this.onTap, super.key});

  final ReportItem item;
  final VoidCallback? onTap;

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
  Widget build(BuildContext context) {
    final c = context.colors;
    final s = _style(context);
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.s16),
        decoration: BoxDecoration(
          color: c.bgCard,
          borderRadius: BorderRadius.circular(AppRadius.r16),
          border: Border.all(color: c.line),
        ),
        child: Row(
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
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.title,
                    style: AppTypography.bodyL.copyWith(
                      color: c.ink,
                      fontWeight: FontWeight.w600,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: AppSpacing.s4 - 1),
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          item.meta,
                          style: AppTypography.bodyS.copyWith(
                            color: c.inkMuted,
                            fontSize: 11,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      const SizedBox(width: AppSpacing.s6),
                      _Badge(status: item.status),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: AppSpacing.s8),
            Icon(Icons.chevron_right, size: 18, color: c.inkFaint),
          ],
        ),
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
