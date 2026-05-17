import 'package:flutter/material.dart';

import '../../../../models/dashboard_summary.dart';
import '../../../../theme/app_theme.dart';

/// Stats row — 3 stat mini (`docs/06-SCREENS.md` → Stats Row &
/// mockup `.stats-row`).
///
/// Warna delta: revenue/order naik = hijau; cost naik = merah (dibalik);
/// flat = muted.
class StatsRow extends StatelessWidget {
  const StatsRow({required this.stats, super.key});

  final List<QuickStat> stats;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.s20,
        0,
        AppSpacing.s20,
        AppSpacing.s20,
      ),
      child: Row(
        children: [
          for (var i = 0; i < stats.length; i++) ...[
            if (i > 0) const SizedBox(width: AppSpacing.s8),
            Expanded(child: _StatMiniCell(stat: stats[i])),
          ],
        ],
      ),
    );
  }
}

class _StatMiniCell extends StatelessWidget {
  const _StatMiniCell({required this.stat});

  final QuickStat stat;

  ({Color color, IconData? icon}) _delta(BuildContext context) {
    final c = context.colors;
    switch (stat.direction) {
      case TrendDirection.flat:
        return (color: c.inkMuted, icon: null);
      case TrendDirection.up:
        return (
          color: stat.isCost ? c.red : c.green,
          icon: Icons.arrow_upward,
        );
      case TrendDirection.down:
        return (
          color: stat.isCost ? c.green : c.red,
          icon: Icons.arrow_downward,
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final delta = _delta(context);
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.s12,
        vertical: AppSpacing.s14,
      ),
      decoration: BoxDecoration(
        color: context.colors.bgCard,
        borderRadius: BorderRadius.circular(AppRadius.r14),
        border: Border.all(color: context.colors.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            stat.label.toUpperCase(),
            style: AppTypography.labelS.copyWith(
              color: context.colors.inkMuted,
              fontSize: 9,
            ),
          ),
          const SizedBox(height: AppSpacing.s6),
          RichText(
            text: TextSpan(
              style: AppTypography.numSmall,
              children: [
                TextSpan(text: stat.value),
                TextSpan(
                  text: ' ${stat.unit}',
                  style: AppTypography.bodyS.copyWith(
                    color: context.colors.inkMuted,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.s4),
          Row(
            children: [
              if (delta.icon != null) ...[
                Icon(delta.icon, size: 12, color: delta.color),
                const SizedBox(width: AppSpacing.s4),
              ],
              Flexible(
                child: Text(
                  stat.deltaText,
                  style: AppTypography.bodyS.copyWith(
                    color: delta.color,
                    fontSize: 10,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
