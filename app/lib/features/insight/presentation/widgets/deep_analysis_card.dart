import 'package:flutter/material.dart';

import '../../../../models/insight_detail.dart';
import '../../../../theme/app_theme.dart';
import '../../../../utils/formatters/date_formatter.dart';

/// Kartu analisis mendalam Codi (mockup `.ai-summary` di SCREEN 4).
///
/// Gradient + goldLine, header ikon gradient brand, tiap section =
/// heading tebal inline + body, footer meta + "Tanya Codi →". Tap →
/// [onAskCodi] (buka Chat).
class DeepAnalysisCard extends StatelessWidget {
  const DeepAnalysisCard({
    required this.title,
    required this.author,
    required this.updatedAt,
    required this.sections,
    required this.meta,
    this.onAskCodi,
    super.key,
  });

  final String title;
  final String author;
  final DateTime updatedAt;
  final List<DeepAnalysisSection> sections;
  final String meta;
  final VoidCallback? onAskCodi;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Container(
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
          for (var i = 0; i < sections.length; i++) ...[
            if (i > 0) const SizedBox(height: AppSpacing.s10),
            RichText(
              text: TextSpan(
                style: AppTypography.bodyM.copyWith(
                  color: c.inkDim,
                  height: 1.65,
                ),
                children: [
                  TextSpan(
                    text: '${sections[i].heading} ',
                    style: AppTypography.bodyM.copyWith(
                      color: c.ink,
                      fontWeight: FontWeight.w700,
                      height: 1.65,
                    ),
                  ),
                  TextSpan(text: sections[i].body),
                ],
              ),
            ),
          ],
          const SizedBox(height: AppSpacing.s14),
          _meta(context),
        ],
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
                title,
                style: AppTypography.bodyL.copyWith(
                  color: c.ink,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: AppSpacing.s2),
              Text(
                '$author · ${DateFormatter.relative(updatedAt)}',
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
        border: Border(
          top: BorderSide(color: c.line),
        ),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            meta,
            style: AppTypography.labelS.copyWith(color: c.inkFaint),
          ),
          GestureDetector(
            onTap: onAskCodi,
            behavior: HitTestBehavior.opaque,
            child: Text(
              'Tanya Codi →',
              style: AppTypography.labelS.copyWith(
                color: c.gold,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
