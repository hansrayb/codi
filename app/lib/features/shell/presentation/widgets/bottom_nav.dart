import 'dart:ui';

import 'package:flutter/material.dart';

import '../../../../theme/app_theme.dart';

/// Item bottom nav.
enum NavTab { beranda, insight, chat, laporan, profil }

/// Bottom navigation **floating** + FAB Codi menonjol keluar.
///
/// Card mengambang (margin + rounded penuh + blur + shadow). FAB Codi
/// keluar ke atas nav (Stack `clipBehavior: none`). 5 slot: 2 item ·
/// FAB · 2 item. **Visual only** MVP — routing di-wire saat go_router
/// siap (Fase 2, `docs/07-ROADMAP.md`).
class BottomNav extends StatelessWidget {
  const BottomNav({
    required this.active,
    this.onTap,
    this.onFabTap,
    super.key,
  });

  final NavTab active;
  final ValueChanged<NavTab>? onTap;

  /// Tap FAB Codi → navigate ke Chat.
  final VoidCallback? onFabTap;

  static const double _barHeight = 64;
  static const double _fabSize = 60;

  /// Berapa FAB nongol di atas bar (px).
  static const double _fabRise = 22;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final safeBottom = MediaQuery.viewPaddingOf(context).bottom;

    return Padding(
      padding: EdgeInsets.fromLTRB(
        AppSpacing.s16,
        0,
        AppSpacing.s16,
        (safeBottom > 0 ? safeBottom : AppSpacing.s16) + AppSpacing.s4,
      ),
      child: SizedBox(
        height: _barHeight + _fabRise,
        child: Stack(
          clipBehavior: Clip.none,
          alignment: Alignment.bottomCenter,
          children: [
            _bar(c),
            Positioned(top: 0, child: _fab(context)),
          ],
        ),
      ),
    );
  }

  Widget _bar(AppColors c) {
    return Align(
      alignment: Alignment.bottomCenter,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(AppRadius.r28),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 24, sigmaY: 24),
          child: Container(
            height: _barHeight,
            decoration: BoxDecoration(
              color: c.bgElev.withValues(alpha: 0.88),
              borderRadius: BorderRadius.circular(AppRadius.r28),
              border: Border.all(color: c.line),
              boxShadow: AppElevation.elev3,
            ),
            child: Row(
              children: [
                Expanded(
                  child: _item(
                    c,
                    NavTab.beranda,
                    Icons.home_outlined,
                    'Beranda',
                  ),
                ),
                Expanded(
                  child: _item(
                    c,
                    NavTab.insight,
                    Icons.insights_outlined,
                    'Insight',
                  ),
                ),
                const SizedBox(width: _fabSize + AppSpacing.s12),
                Expanded(
                  child: _item(
                    c,
                    NavTab.laporan,
                    Icons.description_outlined,
                    'Laporan',
                  ),
                ),
                Expanded(
                  child: _item(
                    c,
                    NavTab.profil,
                    Icons.person_outline,
                    'Profil',
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _item(AppColors c, NavTab tab, IconData icon, String label) {
    final isActive = tab == active;
    final color = isActive ? c.gold : c.inkFaint;
    return GestureDetector(
      onTap: onTap == null ? null : () => onTap!(tab),
      behavior: HitTestBehavior.opaque,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 22, color: color),
          const SizedBox(height: AppSpacing.s4),
          Text(
            label,
            style: AppTypography.labelS.copyWith(
              color: color,
              letterSpacing: 0,
              fontSize: 10,
            ),
          ),
        ],
      ),
    );
  }

  Widget _fab(BuildContext context) {
    final c = context.colors;
    return GestureDetector(
      onTap: onFabTap,
      child: Container(
        width: _fabSize,
        height: _fabSize,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [c.goldBright, c.gold],
          ),
          border: Border.all(color: c.bgApp, width: 3),
          boxShadow: AppElevation.elev2,
        ),
        child: Icon(Icons.auto_awesome, size: 24, color: c.bgApp),
      ),
    );
  }
}
