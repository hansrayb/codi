import 'package:flutter/material.dart';

import 'app_colors.dart';

/// ThemeExtension pembungkus [AppColors] agar resolve per theme
/// (dark/light) via `Theme.of(context)`.
@immutable
class AppPalette extends ThemeExtension<AppPalette> {
  const AppPalette(this.colors);

  final AppColors colors;

  static const AppPalette darkExt = AppPalette(AppColors.dark);
  static const AppPalette lightExt = AppPalette(AppColors.light);

  @override
  AppPalette copyWith({AppColors? colors}) =>
      AppPalette(colors ?? this.colors);

  @override
  AppPalette lerp(ThemeExtension<AppPalette>? other, double t) {
    // Tanpa interpolasi antar set — snap di tengah (theme switch
    // diskret, bukan animasi warna granular).
    if (other is! AppPalette) return this;
    return t < 0.5 ? this : other;
  }
}

/// Akses palet warna theme-aware: `context.colors.bgApp`.
extension AppPaletteX on BuildContext {
  AppColors get colors =>
      Theme.of(this).extension<AppPalette>()?.colors ?? AppColors.dark;
}
