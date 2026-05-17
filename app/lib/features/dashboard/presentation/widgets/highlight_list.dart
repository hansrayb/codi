import 'package:flutter/material.dart';

import '../../../../models/dashboard_summary.dart';
import '../../../../theme/app_theme.dart';
import '../../../../utils/formatters/date_formatter.dart';

/// Section Sorotan (`docs/06-SCREENS.md` → Highlights & mockup
/// `.highlight-list`).
///
/// Title + "Lihat semua →" + list item dengan left-border berwarna
/// severity, icon wrap, timestamp mono.
class HighlightList extends StatelessWidget {
  const HighlightList({
    required this.highlights,
    this.onSeeAll,
    super.key,
  });

  final List<Highlight> highlights;
  final VoidCallback? onSeeAll;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.s20,
            AppSpacing.s12,
            AppSpacing.s20,
            AppSpacing.s12,
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Sorotan',
                style: AppTypography.headlineS,
              ),
              GestureDetector(
                onTap: onSeeAll,
                child: Text(
                  'Lihat semua →',
                  style: AppTypography.bodyS.copyWith(
                    color: AppColors.gold,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ],
          ),
        ),
        for (var i = 0; i < highlights.length; i++)
          Padding(
            padding: EdgeInsets.fromLTRB(
              AppSpacing.s20,
              0,
              AppSpacing.s20,
              i == highlights.length - 1 ? 0 : AppSpacing.s8,
            ),
            child: _HighlightItem(item: highlights[i]),
          ),
      ],
    );
  }
}

class _HighlightItem extends StatelessWidget {
  const _HighlightItem({required this.item});

  final Highlight item;

  ({Color accent, Color soft, IconData icon}) get _style {
    switch (item.severity) {
      case HighlightSeverity.green:
        return (
          accent: AppColors.green,
          soft: AppColors.greenSoft,
          icon: Icons.trending_up,
        );
      case HighlightSeverity.red:
        return (
          accent: AppColors.red,
          soft: AppColors.redSoft,
          icon: Icons.warning_amber_rounded,
        );
      case HighlightSeverity.gold:
        return (
          accent: AppColors.gold,
          soft: AppColors.goldSoft,
          icon: Icons.attach_money,
        );
      case HighlightSeverity.navy:
        return (
          accent: AppColors.navyBlue,
          soft: AppColors.navySoft,
          icon: Icons.groups_outlined,
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = _style;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(AppRadius.r14),
        border: Border.all(color: AppColors.line),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(AppRadius.r14),
        child: IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Container(width: 3, color: s.accent),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.all(AppSpacing.s14),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: 32,
                        height: 32,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          color: s.soft,
                          borderRadius:
                              BorderRadius.circular(AppRadius.r10),
                        ),
                        child: Icon(s.icon, size: 16, color: s.accent),
                      ),
                      const SizedBox(width: AppSpacing.s12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              item.title,
                              style: AppTypography.bodyL.copyWith(
                                color: AppColors.ink,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(height: AppSpacing.s4),
                            Text(
                              item.description,
                              style: AppTypography.bodyS.copyWith(
                                color: AppColors.inkMuted,
                              ),
                            ),
                            const SizedBox(height: AppSpacing.s6),
                            Text(
                              DateFormatter.dayMonthTime(item.timestamp),
                              style: AppTypography.mono,
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
