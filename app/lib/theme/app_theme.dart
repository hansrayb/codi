import 'package:flutter/material.dart';

import 'app_colors.dart';
import 'app_palette.dart';
import 'app_radius.dart';
import 'app_typography.dart';

export 'app_colors.dart';
export 'app_elevation.dart';
export 'app_palette.dart';
export 'app_radius.dart';
export 'app_spacing.dart';
export 'app_typography.dart';

/// Theme Emas Berlian Insight — **light & dark** (brand biru-cyan,
/// `docs/emas-berlian-insight.html`). Theme mode ikut sistem.
abstract final class AppTheme {
  const AppTheme._();

  static ThemeData get darkTheme =>
      _build(AppColors.dark, Brightness.dark, AppPalette.darkExt);

  static ThemeData get lightTheme =>
      _build(AppColors.light, Brightness.light, AppPalette.lightExt);

  static ThemeData _build(
    AppColors c,
    Brightness brightness,
    AppPalette palette,
  ) {
    final base = ThemeData(brightness: brightness, useMaterial3: true);

    final colorScheme = ColorScheme(
      brightness: brightness,
      primary: c.gold,
      onPrimary: brightness == Brightness.dark ? c.bgApp : c.ink,
      secondary: c.navyBlue,
      onSecondary: c.ink,
      surface: c.bgCard,
      onSurface: c.ink,
      error: c.red,
      onError: c.ink,
      outline: c.lineStrong,
    );

    return base.copyWith(
      colorScheme: colorScheme,
      scaffoldBackgroundColor: c.bgApp,
      canvasColor: c.bgApp,
      splashColor: c.goldSoft,
      highlightColor: c.bgHighlight,
      dividerColor: c.line,
      textTheme: _textTheme(c.ink),
      extensions: [palette],
      appBarTheme: AppBarTheme(
        backgroundColor: c.bgApp,
        foregroundColor: c.ink,
        elevation: 0,
        centerTitle: false,
      ),
      dialogTheme: DialogThemeData(backgroundColor: c.bgElev),
      bottomSheetTheme: BottomSheetThemeData(backgroundColor: c.bgElev),
      iconTheme: IconThemeData(color: c.inkDim),
      progressIndicatorTheme: ProgressIndicatorThemeData(color: c.gold),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: c.bgElev,
        contentTextStyle: AppTypography.bodyM.copyWith(color: c.inkDim),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppRadius.r12),
        ),
      ),
    );
  }

  static TextTheme _textTheme(Color ink) {
    TextStyle s(TextStyle t) => t.copyWith(color: ink);
    return TextTheme(
      displayLarge: s(AppTypography.displayXL),
      displayMedium: s(AppTypography.displayL),
      headlineLarge: s(AppTypography.headlineL),
      headlineMedium: s(AppTypography.headlineM),
      headlineSmall: s(AppTypography.headlineS),
      titleLarge: s(AppTypography.headlineM),
      bodyLarge: s(AppTypography.bodyL),
      bodyMedium: s(AppTypography.bodyM),
      bodySmall: s(AppTypography.bodyS),
      labelMedium: s(AppTypography.labelM),
      labelSmall: s(AppTypography.labelS),
    );
  }
}
