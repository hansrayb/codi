import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';

import '../theme/app_theme.dart';

/// Blok skeleton dengan efek shimmer.
///
/// Loading state pakai skeleton, bukan spinner kosong
/// (`docs/02-SPEC.md` → Loading State).
class EmasSkeleton extends StatelessWidget {
  const EmasSkeleton({
    required this.width,
    required this.height,
    this.radius = AppRadius.r8,
    super.key,
  });

  /// Lebar blok.
  final double width;

  /// Tinggi blok.
  final double height;

  /// Border radius — default `r8`.
  final double radius;

  @override
  Widget build(BuildContext context) {
    return Shimmer.fromColors(
      baseColor: AppColors.bgCard,
      highlightColor: AppColors.bgHighlight,
      child: Container(
        width: width,
        height: height,
        decoration: BoxDecoration(
          color: AppColors.bgCard,
          borderRadius: BorderRadius.circular(radius),
        ),
      ),
    );
  }
}

/// Skeleton card siap pakai — meniru layout card umum
/// (judul + 2 baris teks).
class EmasLoadingCard extends StatelessWidget {
  const EmasLoadingCard({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.s14),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(AppRadius.r14),
        border: Border.all(color: AppColors.line),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          EmasSkeleton(width: 140, height: 16),
          SizedBox(height: AppSpacing.s12),
          EmasSkeleton(width: double.infinity, height: 12),
          SizedBox(height: AppSpacing.s8),
          EmasSkeleton(width: 200, height: 12),
        ],
      ),
    );
  }
}
