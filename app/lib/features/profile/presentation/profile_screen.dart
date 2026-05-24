import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
import '../../shell/presentation/widgets/bottom_nav.dart';
import '../application/profile_controller.dart';
import 'widgets/profile_hero.dart';
import 'widgets/settings_card.dart';

/// Profil (S6) — `docs/06-SCREENS.md`, layout match mockup
/// `docs/emas-berlian-insight.html` SCREEN 6.
///
/// Identitas direksi + preferensi (toggle in-memory) + info sesi Codi
/// + logout. Data lokal instan (tak ada async load). Nav di-host shell.
class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({
    this.onOpenChat,
    this.onNavTap,
    this.onLogout,
    this.showBottomNav = true,
    super.key,
  });

  /// Tap FAB Codi → Chat.
  final VoidCallback? onOpenChat;

  /// Tap item bottom nav lain (di-handle shell).
  final ValueChanged<NavTab>? onNavTap;

  /// Tap "Keluar" → kembali ke Login (di-handle shell).
  final VoidCallback? onLogout;

  /// Render BottomNav internal. AppShell set `false`.
  final bool showBottomNav;

  /// Ikon per item id (mockup masing-masing row).
  static IconData _iconFor(String id) {
    switch (id) {
      case 'identitas':
        return Icons.person_outline;
      case 'perusahaan':
        return Icons.apartment_outlined;
      case 'tema':
        return Icons.dark_mode_outlined;
      case 'notifikasi':
        return Icons.notifications_outlined;
      case 'refresh':
        return Icons.sync;
      case 'sesi':
        return Icons.auto_awesome;
      case 'tentang':
        return Icons.info_outline;
      default:
        return Icons.settings_outlined;
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final data = ref.watch(profileControllerProvider);
    final ctrl = ref.read(profileControllerProvider.notifier);
    final c = context.colors;

    return Scaffold(
      body: Stack(
        children: [
          SafeArea(
            bottom: false,
            child: ListView(
              padding: EdgeInsets.only(
                bottom: 116 + MediaQuery.viewPaddingOf(context).bottom,
              ),
              children: [
                ProfileHero(
                  name: data.name,
                  initials: data.initials,
                  role: data.role,
                  org: data.org,
                ),
                for (final g in data.groups)
                  SettingsGroupView(
                    group: g,
                    iconFor: _iconFor,
                    onToggle: ctrl.toggle,
                    onTapItem: (_) {},
                  ),
                _LogoutButton(onTap: onLogout),
                Padding(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.s20,
                    AppSpacing.s16,
                    AppSpacing.s20,
                    AppSpacing.s8,
                  ),
                  child: Text(
                    '${data.footer}\nUntuk Bapak ${data.name}',
                    textAlign: TextAlign.center,
                    style: AppTypography.labelS.copyWith(
                      color: c.inkFaint,
                      fontSize: 10,
                      letterSpacing: 1,
                    ),
                  ),
                ),
              ],
            ),
          ),
          if (showBottomNav)
            Positioned(
              left: 0,
              right: 0,
              bottom: 0,
              child: BottomNav(
                active: NavTab.profil,
                onTap: onNavTap,
                onFabTap: onOpenChat,
              ),
            ),
        ],
      ),
    );
  }
}

class _LogoutButton extends StatelessWidget {
  const _LogoutButton({this.onTap});

  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.s20,
        AppSpacing.s24,
        AppSpacing.s20,
        AppSpacing.s8,
      ),
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: Container(
          padding: const EdgeInsets.all(AppSpacing.s14),
          decoration: BoxDecoration(
            color: c.redSoft,
            borderRadius: BorderRadius.circular(AppRadius.r14),
            border: Border.all(color: c.red.withValues(alpha: 0.3)),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.logout, size: 16, color: c.red),
              const SizedBox(width: AppSpacing.s8),
              Text(
                'Keluar',
                style: AppTypography.bodyL.copyWith(
                  color: c.red,
                  fontWeight: FontWeight.w600,
                  fontSize: 13,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
