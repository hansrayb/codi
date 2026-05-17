import 'package:flutter/material.dart';

import '../../../../models/chat_message.dart';
import '../../../../theme/app_theme.dart';
import '../../../../widgets/charts/emas_sparkline.dart';

/// Rich card di dalam pesan bot (`docs/06-SCREENS.md` → Rich Card &
/// mockup `.rich-card`).
///
/// Header (title uppercase + badge pill), rows (dashed divider, value
/// colored by trend), inline sparkline opsional, action buttons.
class RichCardView extends StatelessWidget {
  const RichCardView({
    required this.card,
    this.onAction,
    super.key,
  });

  final RichCard card;
  final ValueChanged<RichAction>? onAction;

  ({Color fg, Color bg}) _badgeStyle(BuildContext context) {
    final c = context.colors;
    switch (card.badgeColor) {
      case RichBadgeColor.green:
        return (fg: c.green, bg: c.greenSoft);
      case RichBadgeColor.red:
        return (fg: c.red, bg: c.redSoft);
      case RichBadgeColor.gold:
        return (fg: c.gold, bg: c.goldSoft);
    }
  }

  Color _valueColor(BuildContext context, RichTrend t) {
    switch (t) {
      case RichTrend.up:
        return context.colors.green;
      case RichTrend.down:
        return context.colors.red;
      case RichTrend.neutral:
        return context.colors.ink;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.s14),
      decoration: BoxDecoration(
        color: context.colors.bgElev,
        borderRadius: BorderRadius.circular(AppRadius.r14),
        border: Border.all(color: context.colors.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _header(context),
          const SizedBox(height: AppSpacing.s10),
          for (var i = 0; i < card.rows.length; i++)
            _row(context, card.rows[i], isLast: i == card.rows.length - 1),
          if (card.sparkline.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.s12),
            Container(
              padding: const EdgeInsets.all(AppSpacing.s12),
              decoration: BoxDecoration(
                color: context.colors.bgApp,
                borderRadius: BorderRadius.circular(AppRadius.r10),
              ),
              child: EmasSparkline(points: card.sparkline, height: 60),
            ),
          ],
          if (card.actions.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.s12),
            Row(
              children: [
                for (var i = 0; i < card.actions.length; i++) ...[
                  if (i > 0) const SizedBox(width: AppSpacing.s8),
                  Expanded(
                    child: _actionButton(context, card.actions[i]),
                  ),
                ],
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _header(BuildContext context) {
    final b = _badgeStyle(context);
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Expanded(
          child: Text(
            card.title.toUpperCase(),
            style: AppTypography.labelS.copyWith(
              color: context.colors.inkMuted,
              letterSpacing: 1,
            ),
          ),
        ),
        if (card.badge != null)
          Container(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.s8,
              vertical: 3,
            ),
            decoration: BoxDecoration(
              color: b.bg,
              borderRadius: BorderRadius.circular(AppRadius.r4 + 2),
            ),
            child: Text(
              card.badge!,
              style: AppTypography.labelS.copyWith(
                color: b.fg,
                letterSpacing: 0.5,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
      ],
    );
  }

  Widget _row(BuildContext context, RichRow r, {required bool isLast}) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.s8 + 1),
      decoration: BoxDecoration(
        border: isLast
            ? null
            : Border(
                bottom: BorderSide(color: context.colors.line),
              ),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            r.label,
            style: AppTypography.bodyS.copyWith(color: context.colors.inkDim),
          ),
          Text(
            r.value,
            style: AppTypography.bodyS.copyWith(
              color: _valueColor(context, r.trend),
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Widget _actionButton(BuildContext context, RichAction a) {
    return GestureDetector(
      onTap: onAction == null ? null : () => onAction!(a),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.s8 + 1),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: a.primary ? context.colors.goldSoft : Colors.transparent,
          border: Border.all(
            color:
                a.primary ? context.colors.gold : context.colors.lineStrong,
          ),
          borderRadius: BorderRadius.circular(AppRadius.r10),
        ),
        child: Text(
          a.label,
          style: AppTypography.labelM.copyWith(
            color: a.primary ? context.colors.gold : context.colors.inkDim,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}
