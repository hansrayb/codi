import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../../../../theme/app_theme.dart';

/// Logo Login sesuai mockup `docs/emas-berlian-insight.html` (`.login-logo`).
///
/// Container 96x96, radius 28, gradient `bgElev → bgApp`, border `goldLine`,
/// glow gold di belakang (CSS `::before` blur). SVG 52x52 dari
/// `assets/svg/logo.svg`.
class LoginLogo extends StatelessWidget {
  const LoginLogo({super.key});

  static const double _size = 96;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: _size + 24,
      height: _size + 24,
      child: Stack(
        alignment: Alignment.center,
        children: [
          // Glow gold di belakang (CSS ::before: blur 10px, opacity 0.4).
          Container(
            width: _size + 4,
            height: _size + 4,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(AppRadius.r28 + 2),
              boxShadow: const [
                BoxShadow(
                  color: AppColors.goldSoft,
                  blurRadius: 24,
                  spreadRadius: 2,
                ),
              ],
            ),
          ),
          Container(
            width: _size,
            height: _size,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [AppColors.bgElev, AppColors.bgApp],
              ),
              borderRadius: BorderRadius.circular(AppRadius.r28),
              border: Border.all(color: AppColors.goldLine),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x404A7BC8),
                  offset: Offset(0, 10),
                  blurRadius: 40,
                ),
              ],
            ),
            child: SvgPicture.asset(
              'assets/svg/logo.svg',
              width: 52,
              height: 52,
            ),
          ),
        ],
      ),
    );
  }
}
