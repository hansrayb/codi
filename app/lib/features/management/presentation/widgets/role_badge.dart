import 'package:flutter/material.dart';

import '../../../../theme/app_theme.dart';

/// Badge warna per role slug.
class RoleBadge extends StatelessWidget {
  const RoleBadge(this.roleSlug, {super.key});

  final String roleSlug;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final (label, bg, fg) = switch (roleSlug) {
      'superadmin' => ('IT Supervisor', c.goldSoft, c.gold),
      'admin' => ('Admin', c.navySoft, c.navyBlue),
      'director' => ('Direksi', c.navySoft, c.navyBlue),
      'viewer' => ('Viewer', c.bgElev, c.inkMuted),
      _ => (roleSlug, c.bgElev, c.inkMuted),
    };
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.s8,
        vertical: 2,
      ),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(AppRadius.r12),
      ),
      child: Text(
        label,
        style: AppTypography.labelS.copyWith(
          color: fg,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
