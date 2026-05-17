import 'package:flutter/material.dart';

import '../../../../models/dashboard_summary.dart';
import '../../../../theme/app_theme.dart';
import '../../../../utils/formatters/date_formatter.dart';

/// AI Summary card dari Codi (`docs/06-SCREENS.md` → AI Summary Card &
/// mockup `.ai-summary`).
///
/// Gradient + goldLine, header ikon gradient brand, 3 paragraf, footer
/// meta + "Tap untuk detail →". Tap → [onTap] (navigate ke Insight).
class AiSummaryCard extends StatelessWidget {
  const AiSummaryCard({
    required this.summary,
    this.onTap,
    super.key,
  });

  final AiSummary summary;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        margin: const EdgeInsets.fromLTRB(
          AppSpacing.s20,
          0,
          AppSpacing.s20,
          AppSpacing.s16,
        ),
        padding: const EdgeInsets.all(AppSpacing.s16 + 2),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [c.bgCard, c.bgElev],
          ),
          borderRadius: BorderRadius.circular(AppRadius.r16),
          border: Border.all(color: c.goldLine),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _head(context),
            const SizedBox(height: AppSpacing.s12),
            for (var i = 0; i < summary.paragraphs.length; i++) ...[
              if (i > 0) const SizedBox(height: AppSpacing.s8),
              Text(
                summary.paragraphs[i],
                style: AppTypography.bodyM.copyWith(height: 1.65),
              ),
            ],
            const SizedBox(height: AppSpacing.s14),
            _meta(context),
          ],
        ),
      ),
    );
  }

  Widget _head(BuildContext context) {
    final c = context.colors;
    return Row(
      children: [
        Container(
          width: 28,
          height: 28,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [c.gold, c.goldDim],
            ),
            borderRadius: BorderRadius.circular(AppRadius.r8),
          ),
          child: Icon(Icons.auto_awesome, size: 15, color: c.bgApp),
        ),
        const SizedBox(width: AppSpacing.s12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Ringkasan Hari Ini',
                style: AppTypography.bodyL.copyWith(
                  color: c.ink,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: AppSpacing.s2),
              Text(
                'Diperbarui ${DateFormatter.relative(summary.updatedAt)} '
                'oleh Codi',
                style: AppTypography.bodyS.copyWith(
                  color: c.inkMuted,
                  fontSize: 10,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _meta(BuildContext context) {
    final c = context.colors;
    return Container(
      padding: const EdgeInsets.only(top: AppSpacing.s14),
      decoration: BoxDecoration(
        border: Border(top: BorderSide(color: c.line)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            'Berdasarkan ${summary.dataPoints} data point',
            style: AppTypography.labelS.copyWith(color: c.inkFaint),
          ),
          Text(
            'Tap untuk detail →',
            style: AppTypography.labelS.copyWith(
              color: c.gold,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
