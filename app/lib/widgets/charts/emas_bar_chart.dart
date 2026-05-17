import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../../models/dashboard_summary.dart';
import '../../theme/app_theme.dart';

/// Bar chart 7 hari sesuai `docs/03-DESIGN-SYSTEM.md` (Chart Style → Bar)
/// & mockup `.chart-svg`.
///
/// Group per hari: retail (gold) + rotasi (navy) berdampingan. Grid line
/// dashed samar, label hari mono. Animasi 600ms ease-out.
class EmasBarChart extends StatelessWidget {
  const EmasBarChart({
    required this.bars,
    this.height = 130,
    super.key,
  });

  /// Data per hari.
  final List<ChartBar> bars;

  /// Tinggi chart.
  final double height;

  @override
  Widget build(BuildContext context) {
    if (bars.isEmpty) return SizedBox(height: height);

    final maxY = bars
            .map((b) => b.retail > b.rotasi ? b.retail : b.rotasi)
            .reduce((a, b) => a > b ? a : b) *
        1.15;

    return SizedBox(
      height: height,
      child: BarChart(
        BarChartData(
          maxY: maxY,
          alignment: BarChartAlignment.spaceAround,
          barTouchData: BarTouchData(enabled: false),
          gridData: FlGridData(
            show: true,
            drawVerticalLine: false,
            horizontalInterval: maxY / 3,
            getDrawingHorizontalLine: (_) => const FlLine(
              color: Color(0x0AFFFFFF),
              strokeWidth: 1,
              dashArray: [2, 3],
            ),
          ),
          borderData: FlBorderData(show: false),
          titlesData: FlTitlesData(
            leftTitles: const AxisTitles(
              sideTitles: SideTitles(showTitles: false),
            ),
            topTitles: const AxisTitles(
              sideTitles: SideTitles(showTitles: false),
            ),
            rightTitles: const AxisTitles(
              sideTitles: SideTitles(showTitles: false),
            ),
            bottomTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 22,
                getTitlesWidget: (value, meta) {
                  final i = value.toInt();
                  if (i < 0 || i >= bars.length) {
                    return const SizedBox.shrink();
                  }
                  return Padding(
                    padding: const EdgeInsets.only(top: AppSpacing.s6),
                    child: Text(
                      bars[i].label,
                      style: AppTypography.mono.copyWith(
                        color: context.colors.inkMuted,
                      ),
                    ),
                  );
                },
              ),
            ),
          ),
          barGroups: [
            for (var i = 0; i < bars.length; i++)
              BarChartGroupData(
                x: i,
                barsSpace: 3,
                barRods: [
                  BarChartRodData(
                    toY: bars[i].retail,
                    color: context.colors.gold.withValues(alpha: 0.85),
                    width: 9,
                    borderRadius: const BorderRadius.vertical(
                      top: Radius.circular(2),
                    ),
                  ),
                  BarChartRodData(
                    toY: bars[i].rotasi,
                    color: context.colors.navyBlue.withValues(alpha: 0.8),
                    width: 9,
                    borderRadius: const BorderRadius.vertical(
                      top: Radius.circular(2),
                    ),
                  ),
                ],
              ),
          ],
        ),
        swapAnimationDuration: const Duration(milliseconds: 600),
        swapAnimationCurve: Curves.easeOutCubic,
      ),
    );
  }
}
