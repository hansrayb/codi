import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../../../models/insight_detail.dart';
import '../../../../theme/app_theme.dart';

/// Kartu donut komposisi omzet (mockup `.donut-card`).
///
/// Donut digambar `CustomPainter` (tanpa dependency chart). Legend di
/// kanan: caption + tiap slice (swatch · label · persen).
class CompositionDonut extends StatelessWidget {
  const CompositionDonut({
    required this.totalLabel,
    required this.totalUnit,
    required this.caption,
    required this.slices,
    super.key,
  });

  final String totalLabel;
  final String totalUnit;
  final String caption;
  final List<DonutSlice> slices;

  Color _sliceColor(BuildContext context, DonutColor c) {
    final colors = context.colors;
    return switch (c) {
      DonutColor.gold => colors.gold,
      DonutColor.navy => colors.navyBlue,
    };
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Container(
      margin: const EdgeInsets.symmetric(
        horizontal: AppSpacing.s20,
        vertical: AppSpacing.s12,
      ),
      padding: const EdgeInsets.all(AppSpacing.s16 + 2),
      decoration: BoxDecoration(
        color: c.bgCard,
        borderRadius: BorderRadius.circular(AppRadius.r16),
        border: Border.all(color: c.line),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 100,
            height: 100,
            child: CustomPaint(
              painter: _DonutPainter(
                slices: [
                  for (final s in slices)
                    (
                      percent: s.percent,
                      color: _sliceColor(context, s.color),
                    ),
                ],
                trackColor: c.line,
              ),
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    RichText(
                      text: TextSpan(
                        style: AppTypography.numSmall.copyWith(
                          color: c.ink,
                          fontSize: 20,
                        ),
                        children: [
                          TextSpan(text: totalLabel),
                          TextSpan(
                            text: totalUnit,
                            style: AppTypography.bodyS.copyWith(
                              color: c.inkMuted,
                              fontSize: 10,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: AppSpacing.s2),
                    Text(
                      'TOTAL',
                      style: AppTypography.labelS.copyWith(
                        color: c.inkMuted,
                        fontSize: 9,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          const SizedBox(width: AppSpacing.s16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  caption.toUpperCase(),
                  style: AppTypography.labelS.copyWith(
                    color: c.inkMuted,
                    fontSize: 10,
                  ),
                ),
                const SizedBox(height: AppSpacing.s8),
                for (var i = 0; i < slices.length; i++) ...[
                  if (i > 0) const SizedBox(height: AppSpacing.s8),
                  _LegendRow(
                    slice: slices[i],
                    color: _sliceColor(context, slices[i].color),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _LegendRow extends StatelessWidget {
  const _LegendRow({required this.slice, required this.color});

  final DonutSlice slice;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final pct = slice.percent
        .toStringAsFixed(1)
        .replaceAll('.', ',')
        .replaceAll(',0', '');
    return Row(
      children: [
        Container(
          width: 9,
          height: 9,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(AppRadius.r4 - 1),
          ),
        ),
        const SizedBox(width: AppSpacing.s8),
        Expanded(
          child: Text(
            slice.label,
            style: AppTypography.bodyS.copyWith(color: c.inkDim),
            overflow: TextOverflow.ellipsis,
          ),
        ),
        Text(
          '$pct%',
          style: AppTypography.numSmall.copyWith(
            color: c.ink,
            fontSize: 13,
          ),
        ),
      ],
    );
  }
}

/// Painter donut: track abu + arc per slice, rounded cap, gap kecil.
class _DonutPainter extends CustomPainter {
  _DonutPainter({required this.slices, required this.trackColor});

  final List<({double percent, Color color})> slices;
  final Color trackColor;

  static const double _stroke = 12;
  static const double _gapRad = 0.06;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = (math.min(size.width, size.height) - _stroke) / 2;
    final rect = Rect.fromCircle(center: center, radius: radius);

    final track = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = _stroke
      ..color = trackColor;
    canvas.drawCircle(center, radius, track);

    var start = -math.pi / 2;
    for (final s in slices) {
      final sweep = (s.percent / 100) * 2 * math.pi;
      final arc = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = _stroke
        ..strokeCap = StrokeCap.round
        ..color = s.color;
      canvas.drawArc(
        rect,
        start + _gapRad / 2,
        sweep - _gapRad,
        false,
        arc,
      );
      start += sweep;
    }
  }

  @override
  bool shouldRepaint(_DonutPainter old) =>
      old.slices != slices || old.trackColor != trackColor;
}
