import 'package:flutter/material.dart';

import '../../../../theme/app_theme.dart';

/// Avatar Codi (`docs/06-SCREENS.md` S3 → Header & mockup chat-header).
///
/// Icon aplikasi (`assets/icon/icon-dark.png`) di kotak rounded
/// dengan border brand.
class CodiAvatar extends StatelessWidget {
  const CodiAvatar({this.size = 34, super.key});

  /// Sisi kotak (default 34, sesuai mockup).
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(AppRadius.r10),
        border: Border.all(color: context.colors.goldLine),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(AppRadius.r10),
        child: Image.asset(
          'assets/icon/icon-dark.png',
          width: size,
          height: size,
          fit: BoxFit.cover,
        ),
      ),
    );
  }
}
