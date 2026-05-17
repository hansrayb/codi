import 'package:flutter/material.dart';

import '../../../../theme/app_theme.dart';
import '../../../../widgets/emas_avatar.dart';

/// Greeting + avatar (`docs/06-SCREENS.md` → Greeting & mockup `.top-nav`).
///
/// Sapaan dinamis by jam. Format formal: "Bapak {nama}".
class GreetingHeader extends StatelessWidget {
  const GreetingHeader({
    required this.name,
    required this.title,
    this.now,
    super.key,
  });

  /// Nama user (tanpa "Bapak").
  final String name;

  /// Jabatan, mis. "Direktur Utama".
  final String title;

  /// Override waktu untuk test.
  final DateTime? now;

  String _greeting() {
    final h = (now ?? DateTime.now()).hour;
    if (h >= 4 && h < 11) return 'Selamat pagi,';
    if (h >= 11 && h < 15) return 'Selamat siang,';
    if (h >= 15 && h < 18) return 'Selamat sore,';
    return 'Selamat malam,';
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.s20,
        AppSpacing.s12,
        AppSpacing.s20,
        AppSpacing.s16,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _greeting(),
                  style: AppTypography.bodyS.copyWith(
                    color: AppColors.inkMuted,
                  ),
                ),
                const SizedBox(height: AppSpacing.s2),
                Text(
                  'Bapak $name',
                  style: AppTypography.headlineM.copyWith(fontSize: 17),
                ),
                const SizedBox(height: AppSpacing.s2),
                Text(
                  title.toUpperCase(),
                  style: AppTypography.labelS.copyWith(
                    color: AppColors.gold,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: AppSpacing.s12),
          EmasAvatar(name: name, size: 42),
        ],
      ),
    );
  }
}
