import 'package:flutter/material.dart';

import '../../../../models/insight_detail.dart';
import '../../../../theme/app_theme.dart';

/// Grid KPI 2 kolom (mockup `.kpi-grid` / `.kpi-cell`).
///
/// Warna delta: revenue/order naik = hijau; cost naik = merah (dibalik);
/// flat = muted — konsisten dgn `StatsRow` dashboard.
class KpiGrid extends StatelessWidget {
  const KpiGrid({required this.kpis, super.key});

  final List<InsightKpi> kpis;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.s20,
        0,
        AppSpacing.s20,
        AppSpacing.s8,
      ),
      child: GridView.builder(
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        itemCount: kpis.length,
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 2,
          crossAxisSpacing: AppSpacing.s8,
          mainAxisSpacing: AppSpacing.s8,
          childAspectRatio: 1.55,
        ),
        itemBuilder: (_, i) => _KpiCell(kpi: kpis[i]),
      ),
    );
  }
}

class _KpiCell extends StatelessWidget {
  const _KpiCell({required this.kpi});

  final InsightKpi kpi;

  ({Color color, IconData? icon}) _delta(BuildContext context) {
    final c = context.colors;
    switch (kpi.direction) {
      case TrendDirection.flat:
        return (color: c.inkMuted, icon: null);
      case TrendDirection.up:
        return (
          color: kpi.isCost ? c.red : c.green,
          icon: Icons.keyboard_arrow_up,
        );
      case TrendDirection.down:
        return (
          color: kpi.isCost ? c.red : c.green,
          icon: Icons.keyboard_arrow_down,
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final delta = _delta(context);
    return Container(
      padding: const EdgeInsets.all(AppSpacing.s14),
      decoration: BoxDecoration(
        color: c.bgCard,
        borderRadius: BorderRadius.circular(AppRadius.r14),
        border: Border.all(color: c.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            kpi.label.toUpperCase(),
            style: AppTypography.labelS.copyWith(
              color: c.inkMuted,
              fontSize: 10,
            ),
          ),
          RichText(
            text: TextSpan(
              style: AppTypography.numMedium.copyWith(color: c.ink),
              children: [
                TextSpan(text: kpi.value),
                TextSpan(
                  text: kpi.unit,
                  style: AppTypography.bodyS.copyWith(
                    color: c.inkMuted,
                    fontWeight: FontWeight.w500,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
          Row(
            children: [
              if (delta.icon != null) ...[
                Icon(delta.icon, size: 14, color: delta.color),
                const SizedBox(width: AppSpacing.s4),
              ],
              Flexible(
                child: Text(
                  kpi.deltaText,
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
