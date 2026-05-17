import 'package:flutter/material.dart';

import '../../../../theme/app_theme.dart';

/// Hero header Insight (mockup `.detail-hero`).
///
/// Gradient navy lembut di atas, baris 2 icon-btn (back + export), judul
/// Fraunces, sub periode + dot "Live". Back tap → [onBack].
class InsightHero extends StatelessWidget {
  const InsightHero({
    required this.title,
    required this.periodLabel,
    required this.isLive,
    this.onBack,
    this.onExport,
    super.key,
  });

  final String title;
  final String periodLabel;
  final bool isLive;
  final VoidCallback? onBack;
  final VoidCallback? onExport;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Container(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.s20,
        AppSpacing.s12,
        AppSpacing.s20,
        AppSpacing.s24,
      ),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [c.navySoft, c.bgApp.withValues(alpha: 0)],
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _IconBtn(icon: Icons.arrow_back, onTap: onBack),
              _IconBtn(icon: Icons.ios_share_outlined, onTap: onExport),
            ],
          ),
          const SizedBox(height: AppSpacing.s16 + 2),
          Text(
            title,
            style: AppTypography.headlineL.copyWith(
              color: c.ink,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: AppSpacing.s4),
          RichText(
            text: TextSpan(
              style: AppTypography.bodyS.copyWith(color: c.inkMuted),
              children: [
                TextSpan(text: periodLabel),
                if (isLive)
                  TextSpan(
                    text: ' · Live',
                    style: AppTypography.bodyS.copyWith(
                      color: c.green,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _IconBtn extends StatelessWidget {
  const _IconBtn({required this.icon, this.onTap});

  final IconData icon;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        width: 36,
        height: 36,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: c.bgCard,
          borderRadius: BorderRadius.circular(AppRadius.r12),
          border: Border.all(color: c.line),
        ),
        child: Icon(icon, size: 18, color: c.inkDim),
      ),
    );
  }
}
