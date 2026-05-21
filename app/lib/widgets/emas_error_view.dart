import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import 'emas_button.dart';

/// Error state sesuai `docs/02-SPEC.md` (Error State).
///
/// Pesan ramah (bukan stack trace) + tombol "Coba lagi".
class EmasErrorView extends StatelessWidget {
  const EmasErrorView({
    required this.message,
    this.onRetry,
    this.title = 'Terjadi Kesalahan',
    super.key,
  });

  /// Pesan ramah untuk user.
  final String message;

  /// Callback retry. Null = tombol disembunyikan.
  final VoidCallback? onRetry;

  /// Judul — default "Terjadi Kesalahan".
  final String title;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.s24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 56,
              height: 56,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: context.colors.redSoft,
                borderRadius: BorderRadius.circular(AppRadius.r16),
              ),
              child: Icon(
                Icons.cloud_off_outlined,
                size: 28,
                color: context.colors.red,
              ),
            ),
            const SizedBox(height: AppSpacing.s16),
            Text(
              title,
              style: AppTypography.headlineS,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppSpacing.s8),
            Text(
              message,
              style: AppTypography.bodyM,
              textAlign: TextAlign.center,
            ),
            if (onRetry != null) ...[
              const SizedBox(height: AppSpacing.s24),
              EmasButton(
                label: 'Coba lagi',
                icon: Icons.refresh,
                onPressed: onRetry,
                variant: EmasButtonVariant.secondary,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
