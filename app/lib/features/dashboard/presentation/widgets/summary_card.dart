import 'package:flutter/material.dart';

import '../../../../models/dashboard_summary.dart';
import '../../../../theme/app_theme.dart';
import '../../../../utils/formatters/currency_formatter.dart';
import '../../../../widgets/charts/emas_sparkline.dart';

/// Hero summary card (`docs/06-SCREENS.md` → Hero Summary Card &
/// mockup `.summary-card`).
///
/// Gradient bgCard→bgElev, border goldLine, 2 radial dekoratif, live dot
/// blink, angka besar Fraunces, trend, sparkline.
class SummaryCard extends StatefulWidget {
  const SummaryCard({required this.data, super.key});

  final DashboardSummary data;

  @override
  State<SummaryCard> createState() => _SummaryCardState();
}

class _SummaryCardState extends State<SummaryCard>
    with SingleTickerProviderStateMixin {
  late final AnimationController _blink;

  @override
  void initState() {
    super.initState();
    _blink = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _blink.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final d = widget.data;
    final money = CurrencyFormatter.compact(d.omzet);
    final isUp = d.trendDirection == TrendDirection.up;
    final trendColor = isUp ? AppColors.green : AppColors.red;

    return Container(
      margin: const EdgeInsets.fromLTRB(
        AppSpacing.s20,
        0,
        AppSpacing.s20,
        AppSpacing.s16,
      ),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [AppColors.bgCard, AppColors.bgElev],
        ),
        borderRadius: BorderRadius.circular(AppRadius.r20),
        border: Border.all(color: AppColors.goldLine),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(AppRadius.r20),
        child: Stack(
          children: [
            // Radial dekoratif gold (pojok kanan atas).
            Positioned(
              top: -50,
              right: -50,
              child: _glow(180, AppColors.goldSoft),
            ),
            // Radial dekoratif navy (kiri bawah).
            Positioned(
              bottom: -80,
              left: -50,
              child: _glow(200, AppColors.navySoft),
            ),
            Padding(
              padding: const EdgeInsets.all(AppSpacing.s20 + 2),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _label(d),
                  const SizedBox(height: AppSpacing.s8),
                  _value(money),
                  const SizedBox(height: AppSpacing.s12),
                  _meta(d, isUp, trendColor),
                  const SizedBox(height: AppSpacing.s16),
                  EmasSparkline(points: d.sparkline),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _glow(double size, Color color) => Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: RadialGradient(
            colors: [color, color.withValues(alpha: 0)],
          ),
        ),
      );

  Widget _label(DashboardSummary d) => Row(
        children: [
          FadeTransition(
            opacity: Tween<double>(begin: 1, end: 0.4).animate(_blink),
            child: Container(
              width: 6,
              height: 6,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: AppColors.green,
                boxShadow: [
                  BoxShadow(
                    color: AppColors.green.withValues(alpha: 0.6),
                    blurRadius: 8,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(width: AppSpacing.s6),
          Text(
            'OMZET ${d.periodLabel} · LIVE',
            style: AppTypography.labelS.copyWith(color: AppColors.inkMuted),
          ),
        ],
      );

  Widget _value(({String currency, String number, String unit}) m) {
    return RichText(
      text: TextSpan(
        style: AppTypography.numLarge,
        children: [
          TextSpan(
            text: '${m.currency} ',
            style: AppTypography.numLarge.copyWith(
              fontSize: 16,
              color: AppColors.inkMuted,
              fontWeight: FontWeight.w500,
            ),
          ),
          TextSpan(text: m.number),
          if (m.unit.isNotEmpty)
            TextSpan(
              text: ' ${m.unit}',
              style: AppTypography.numLarge.copyWith(
                fontSize: 18,
                color: AppColors.inkMuted,
                fontWeight: FontWeight.w500,
              ),
            ),
        ],
      ),
    );
  }

  Widget _meta(DashboardSummary d, bool isUp, Color trendColor) {
    return Row(
      children: [
        Icon(
          isUp ? Icons.arrow_upward : Icons.arrow_downward,
          size: 14,
          color: trendColor,
        ),
        const SizedBox(width: AppSpacing.s4),
        Text(
          d.trendText,
          style: AppTypography.bodyS.copyWith(
            color: trendColor,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(width: AppSpacing.s14),
        Expanded(
          child: Text(
            d.periodInfo,
            style: AppTypography.bodyS.copyWith(color: AppColors.inkMuted),
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ],
    );
  }
}
