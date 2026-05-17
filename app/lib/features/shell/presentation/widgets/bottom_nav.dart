import 'dart:ui';

import 'package:flutter/material.dart';

import '../../../../theme/app_theme.dart';

/// Item bottom nav.
enum NavTab { beranda, insight, chat, laporan, profil }

/// Bottom navigation + FAB Codi (`docs/03-DESIGN-SYSTEM.md` → Bottom
/// Navigation & mockup `.bottom-nav`).
///
/// 5 slot: 2 item · FAB Codi (tengah, overflow ke atas) · 2 item.
/// Blur background. **Visual only** untuk MVP — routing antar tab
/// di-wire saat go_router siap (Fase 2, `docs/07-ROADMAP.md`).
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

  @override
  Widget build(BuildContext context) {
    return ClipRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
        child: Container(
          height: 80,
          padding: const EdgeInsets.only(bottom: 24),
          decoration: BoxDecoration(
            color: const Color(0xEB0A1124),
            border: Border(top: BorderSide(color: context.colors.line)),
          ),
          child: Row(
            children: [
              Expanded(
                child: _item(
                  context,
                  NavTab.beranda,
                  Icons.home_outlined,
                  'Beranda',
                ),
              ),
              Expanded(
                child: _item(
                  context,
                  NavTab.insight,
                  Icons.insights_outlined,
                  'Insight',
                ),
              ),
              SizedBox(width: 80, child: _fab(context)),
              Expanded(
                child: _item(
                  context,
                  NavTab.laporan,
                  Icons.description_outlined,
                  'Laporan',
                ),
              ),
              Expanded(
                child: _item(
                  context,
                  NavTab.profil,
                  Icons.person_outline,
                  'Profil',
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _item(
    BuildContext context,
    NavTab tab,
    IconData icon,
    String label,
  ) {
    final isActive = tab == active;
    final color = isActive ? context.colors.gold : context.colors.inkFaint;
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
    return Center(
      child: Transform.translate(
        offset: const Offset(0, -12),
        child: GestureDetector(
          onTap: onFabTap,
          child: Container(
            width: 56,
            height: 56,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [context.colors.goldBright, context.colors.gold],
              ),
              boxShadow: AppElevation.elev2,
            ),
            child: Icon(
              Icons.auto_awesome,
              size: 24,
              color: context.colors.bgApp,
            ),
          ),
        ),
      ),
    );
  }
}
