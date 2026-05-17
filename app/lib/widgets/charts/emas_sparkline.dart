import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../../theme/app_theme.dart';

/// Sparkline sesuai `docs/03-DESIGN-SYSTEM.md` (Chart Style → Sparkline)
/// & mockup `.mini-chart`.
///
/// Garis gold 1.8px, fill gradient gold 0.4 → 0, titik akhir lingkaran
/// gold + halo. Tinggi 50px.
class EmasSparkline extends StatelessWidget {
  const EmasSparkline({
    required this.points,
    this.height = 50,
    super.key,
  });

  /// Nilai y berurutan.
  final List<double> points;

  /// Tinggi area chart.
  final double height;

  @override
  Widget build(BuildContext context) {
    if (points.isEmpty) return SizedBox(height: height);

    final spots = <FlSpot>[
      for (var i = 0; i < points.length; i++)
        FlSpot(i.toDouble(), points[i]),
    ];

    return SizedBox(
      height: height,
      child: LineChart(
        LineChartData(
          minX: 0,
          maxX: (points.length - 1).toDouble(),
          gridData: const FlGridData(show: false),
          titlesData: const FlTitlesData(show: false),
          borderData: FlBorderData(show: false),
          lineTouchData: const LineTouchData(enabled: false),
          lineBarsData: [
            LineChartBarData(
              spots: spots,
              isCurved: true,
              curveSmoothness: 0.3,
              color: context.colors.gold,
              barWidth: 1.8,
              dotData: FlDotData(
                show: true,
                checkToShowDot: (spot, _) => spot.x == spots.last.x,
                getDotPainter: (spot, _, __, ___) => FlDotCirclePainter(
                  radius: 3.5,
                  color: context.colors.gold,
                  strokeWidth: 1,
                  strokeColor: context.colors.gold.withValues(alpha: 0.4),
                ),
              ),
              belowBarData: BarAreaData(
                show: true,
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [
                    context.colors.gold.withValues(alpha: 0.4),
                    context.colors.gold.withValues(alpha: 0.0),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
