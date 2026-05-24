import 'package:flutter/material.dart';

import '../../../../theme/app_theme.dart';

/// Hero profil (mockup `.profile-hero`).
///
/// Avatar inisial besar (gradient navy), nama Fraunces, role uppercase
/// brand, org muted. Gradient navy lembut di atas.
class ProfileHero extends StatelessWidget {
  const ProfileHero({
    required this.name,
    required this.initials,
    required this.role,
    required this.org,
    super.key,
  });

  final String name;
  final String initials;
  final String role;
  final String org;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.s20,
        AppSpacing.s24 + AppSpacing.s4,
        AppSpacing.s20,
        AppSpacing.s24,
      ),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [c.navySoft, c.bgApp.withValues(alpha: 0)],
        ),
      ),
      child: Column(
        children: [
          Container(
            width: 84,
            height: 84,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [c.navyBlue, const Color(0xFF2A4A7F)],
              ),
              border: Border.all(color: c.goldLine, width: 2),
            ),
            child: Text(
              initials,
              style: AppTypography.numMedium.copyWith(
                color: c.ink,
                fontSize: 28,
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.s14),
          Text(
            name,
            style: AppTypography.headlineM.copyWith(
              color: c.ink,
              fontSize: 20,
            ),
          ),
          const SizedBox(height: AppSpacing.s6 - 1),
          Text(
            role.toUpperCase(),
            style: AppTypography.labelS.copyWith(
              color: c.gold,
              fontSize: 11,
            ),
          ),
          const SizedBox(height: AppSpacing.s8),
          Text(
            org,
            style: AppTypography.bodyS.copyWith(color: c.inkMuted),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}
