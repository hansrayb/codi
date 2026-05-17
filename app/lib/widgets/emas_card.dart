import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Card default sesuai `docs/03-DESIGN-SYSTEM.md` (Cards → Default Card).
///
/// Background `bgCard`, border 1px `line`, radius `r14`, padding `s14`.
/// Tap-able jika [onTap] di-set.
class EmasCard extends StatelessWidget {
  const EmasCard({
    required this.child,
    this.padding = const EdgeInsets.all(AppSpacing.s14),
    this.onTap,
    super.key,
  });

  /// Konten card.
  final Widget child;

  /// Padding dalam — default `s14`.
  final EdgeInsetsGeometry padding;

  /// Callback saat di-tap. Null = non-interaktif.
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final card = Container(
      padding: padding,
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(AppRadius.r14),
        border: Border.all(color: AppColors.line),
      ),
      child: child,
    );

    if (onTap == null) return card;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppRadius.r14),
        splashColor: AppColors.goldSoft,
        highlightColor: AppColors.bgHighlight,
        child: card,
      ),
    );
  }
}

/// Card elevated untuk hero / AI summary
/// (`docs/03-DESIGN-SYSTEM.md` → Elevated Card).
///
/// Gradient `bgCard → bgElev`, border `goldLine`, radius `r20`,
/// padding `s20`, shadow `elev3`.
class EmasElevatedCard extends StatelessWidget {
  const EmasElevatedCard({
    required this.child,
    this.padding = const EdgeInsets.all(AppSpacing.s20),
    super.key,
  });

  /// Konten card.
  final Widget child;

  /// Padding dalam — default `s20`.
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [AppColors.bgCard, AppColors.bgElev],
        ),
        borderRadius: BorderRadius.circular(AppRadius.r20),
        border: Border.all(color: AppColors.goldLine),
        boxShadow: AppElevation.elev3,
      ),
      child: child,
    );
  }
}
