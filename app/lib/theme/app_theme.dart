import 'package:flutter/material.dart';

import 'app_colors.dart';
import 'app_radius.dart';
import 'app_typography.dart';

export 'app_colors.dart';
export 'app_elevation.dart';
export 'app_radius.dart';
export 'app_spacing.dart';
export 'app_typography.dart';

/// Theme Emas Berlian Insight — **dark-only** (lihat `docs/03-DESIGN-SYSTEM.md`,
/// bagian Dark Mode). Tidak ada light mode untuk Phase 1.
abstract final class AppTheme {
  const AppTheme._();

  static ThemeData get darkTheme {
    final base = ThemeData.dark(useMaterial3: true);

    const colorScheme = ColorScheme.dark(
      primary: AppColors.gold,
      onPrimary: AppColors.bgApp,
      secondary: AppColors.navyBlue,
      onSecondary: AppColors.ink,
      surface: AppColors.bgCard,
      onSurface: AppColors.ink,
      error: AppColors.red,
      onError: AppColors.ink,
      outline: AppColors.lineStrong,
    );

    return base.copyWith(
      colorScheme: colorScheme,
      scaffoldBackgroundColor: AppColors.bgApp,
      canvasColor: AppColors.bgApp,
      splashColor: AppColors.goldSoft,
      highlightColor: AppColors.bgHighlight,
      dividerColor: AppColors.line,
      textTheme: _textTheme,
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.bgApp,
        foregroundColor: AppColors.ink,
        elevation: 0,
        centerTitle: false,
      ),
      dialogTheme: const DialogThemeData(
        backgroundColor: AppColors.bgElev,
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: AppColors.bgElev,
      ),
      iconTheme: const IconThemeData(color: AppColors.inkDim),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: AppColors.gold,
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: AppColors.bgElev,
        contentTextStyle: AppTypography.bodyM,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppRadius.r12),
        ),
      ),
    );
  }

  static TextTheme get _textTheme => TextTheme(
        displayLarge: AppTypography.displayXL,
        displayMedium: AppTypography.displayL,
        headlineLarge: AppTypography.headlineL,
        headlineMedium: AppTypography.headlineM,
        headlineSmall: AppTypography.headlineS,
        titleLarge: AppTypography.headlineM,
        bodyLarge: AppTypography.bodyL,
        bodyMedium: AppTypography.bodyM,
        bodySmall: AppTypography.bodyS,
        labelMedium: AppTypography.labelM,
        labelSmall: AppTypography.labelS,
      );
}
