import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Tingkat keparahan alert — menentukan warna aksen.
enum EmasAlertSeverity {
  /// Hijau — sehat/positif.
  success,

  /// Amber — perlu perhatian.
  warning,

  /// Merah — kritis/negatif.
  danger,

  /// Navy — informasi netral.
  info,
}

/// Highlight card sesuai `docs/03-DESIGN-SYSTEM.md` (Cards → Highlight Card).
///
/// Border kiri 3px berwarna semantic, ikon 32x32 dengan bg tint.
class EmasAlert extends StatelessWidget {
  const EmasAlert({
    required this.title,
    required this.message,
    this.severity = EmasAlertSeverity.info,
    this.icon,
    super.key,
  });

  /// Judul singkat.
  final String title;

  /// Pesan detail.
  final String message;

  /// Tingkat keparahan.
  final EmasAlertSeverity severity;

  /// Ikon opsional (default per severity).
  final IconData? icon;

  ({Color accent, Color soft, IconData icon}) _style(BuildContext context) {
    final c = context.colors;
    switch (severity) {
      case EmasAlertSeverity.success:
        return (
          accent: c.green,
          soft: c.greenSoft,
          icon: Icons.check_circle_outline,
        );
      case EmasAlertSeverity.warning:
        return (
          accent: c.amber,
          soft: c.amberSoft,
          icon: Icons.warning_amber_outlined,
        );
      case EmasAlertSeverity.danger:
        return (
          accent: c.red,
          soft: c.redSoft,
          icon: Icons.error_outline,
        );
      case EmasAlertSeverity.info:
        return (
          accent: c.navyBlue,
          soft: c.navySoft,
          icon: Icons.info_outline,
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = _style(context);
    // Border kiri 3px berwarna semantic + radius: pakai accent bar terpisah,
    // bukan Border per-sisi (Flutter melarang borderRadius pada border
    // dengan warna sisi non-uniform).
    return DecoratedBox(
      decoration: BoxDecoration(
        color: context.colors.bgCard,
        borderRadius: BorderRadius.circular(AppRadius.r14),
        border: Border.all(color: context.colors.line),
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
                              BorderRadius.circular(AppRadius.r8),
                        ),
                        child: Icon(
                          icon ?? s.icon,
                          size: 18,
                          color: s.accent,
                        ),
                      ),
                      const SizedBox(width: AppSpacing.s12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              title,
                              style: AppTypography.bodyL.copyWith(
                                color: context.colors.ink,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(height: AppSpacing.s4),
                            Text(message, style: AppTypography.bodyS),
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
