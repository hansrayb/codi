import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Empty state sesuai `docs/02-SPEC.md` (Empty State).
///
/// Ilustrasi sederhana + pesan jelas + suggest action opsional.
class EmasEmptyView extends StatelessWidget {
  const EmasEmptyView({
    required this.message,
    this.icon = Icons.inbox_outlined,
    this.action,
    super.key,
  });

  /// Pesan jelas, mis. "Belum ada data untuk periode ini".
  final String message;

  /// Ikon ilustrasi sederhana.
  final IconData icon;

  /// Widget aksi opsional (mis. tombol).
  final Widget? action;

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
                color: AppColors.bgHighlight,
                borderRadius: BorderRadius.circular(AppRadius.r16),
              ),
              child: Icon(icon, size: 28, color: AppColors.inkMuted),
            ),
            const SizedBox(height: AppSpacing.s16),
            Text(
              message,
              style: AppTypography.bodyM,
              textAlign: TextAlign.center,
            ),
            if (action != null) ...[
              const SizedBox(height: AppSpacing.s20),
              action!,
            ],
          ],
        ),
      ),
    );
  }
}
