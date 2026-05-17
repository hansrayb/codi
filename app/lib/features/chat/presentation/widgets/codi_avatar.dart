import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../../../../theme/app_theme.dart';

/// Avatar Codi (`docs/06-SCREENS.md` S3 → Header & mockup chat-header).
///
/// Kotak gradient bgElev→bgApp, border goldLine, SVG mini diamond+gold.
class CodiAvatar extends StatelessWidget {
  const CodiAvatar({this.size = 34, super.key});

  /// Sisi kotak (default 34, sesuai mockup).
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [context.colors.bgElev, context.colors.bgApp],
        ),
        borderRadius: BorderRadius.circular(AppRadius.r10),
        border: Border.all(color: context.colors.goldLine),
      ),
      child: SvgPicture.asset(
        'assets/svg/codi_avatar.svg',
        width: size * 0.6,
        height: size * 0.6,
      ),
    );
  }
}
