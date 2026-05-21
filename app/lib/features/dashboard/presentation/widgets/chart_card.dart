import 'package:flutter/material.dart';

import '../../../../models/dashboard_summary.dart';
import '../../../../theme/app_theme.dart';
import '../../../../widgets/charts/emas_bar_chart.dart';

/// Chart card 7 hari (`docs/06-SCREENS.md` → Chart Card & mockup
/// `.chart-card`).
///
/// Header judul + legend (retail gold / rotasi navy) + bar chart.
class ChartCard extends StatelessWidget {
  const ChartCard({required this.bars, super.key});

  final List<ChartBar> bars;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.fromLTRB(
        AppSpacing.s20,
        0,
        AppSpacing.s20,
        AppSpacing.s16,
      ),
      padding: const EdgeInsets.all(AppSpacing.s16 + 2),
      decoration: BoxDecoration(
        color: context.colors.bgCard,
        borderRadius: BorderRadius.circular(AppRadius.r16),
        border: Border.all(color: context.colors.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Tren Omzet 7 Hari Terakhir',
                      style: AppTypography.bodyL.copyWith(
                        color: context.colors.ink,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.s2),
                    Text(
                      'Penjualan emas vs Rotasi',
                      style: AppTypography.bodyS.copyWith(
                        color: context.colors.inkMuted,
                        fontSize: 10,
                      ),
                    ),
                  ],
                ),
              ),
              _legend(context),
            ],
          ),
          const SizedBox(height: AppSpacing.s14),
          EmasBarChart(bars: bars),
        ],
      ),
    );
  }

  Widget _legend(BuildContext context) => Row(
        children: [
          _swatch(context, context.colors.gold, 'Retail'),
          const SizedBox(width: AppSpacing.s12),
          _swatch(context, context.colors.navyBlue, 'Rotasi'),
        ],
      );

  Widget _swatch(BuildContext context, Color color, String label) => Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: AppSpacing.s4),
          Text(
            label,
            style: AppTypography.bodyS.copyWith(
              color: context.colors.inkDim,
              fontSize: 10,
            ),
          ),
        ],
      );
}
