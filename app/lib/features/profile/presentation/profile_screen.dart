import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/profile_data.dart';
import '../../../providers/token_store.dart';
import '../../../theme/app_theme.dart';
import '../../management/presentation/management_screen.dart';
import '../../shell/presentation/widgets/bottom_nav.dart';
import '../application/profile_controller.dart';
import 'widgets/profile_hero.dart';
import 'widgets/profile_sheets.dart';
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

  /// Dispatch tap baris pengaturan (chevron/value) ke sheet/dialog.
  static void _onTapItem(
    BuildContext context,
    TokenStore tokenStore,
    ProfileData data,
    String id,
  ) {
    switch (id) {
      case 'identitas':
        showIdentitasSheet(context, tokenStore);
      case 'perusahaan':
        showPerusahaanSheet(context, data.org);
      case 'tema':
        showThemePicker(context);
      case 'sesi':
        showSessionsSheet(context);
      case 'tentang':
        showAboutSheet(context);
    }
  }

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
    final tokenStore = ref.read(tokenStoreProvider);
    final canManage = tokenStore.hasScope('accounts:read');
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
                    onTapItem: (id) => _onTapItem(context, tokenStore, data, id),
                  ),
                if (canManage) const _ManagementRow(),
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

class _ManagementRow extends StatelessWidget {
  const _ManagementRow();

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.s20,
        AppSpacing.s8,
        AppSpacing.s20,
        AppSpacing.s4,
      ),
      child: Material(
        color: c.bgElev,
        borderRadius: BorderRadius.circular(AppRadius.r14),
        child: InkWell(
          borderRadius: BorderRadius.circular(AppRadius.r14),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) => const ManagementScreen(),
            ),
          ),
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.s14),
            child: Row(
              children: [
                Icon(Icons.manage_accounts_outlined,
                    size: 20, color: c.gold),
                const SizedBox(width: AppSpacing.s12),
                Expanded(
                  child: Text(
                    'Kelola Akun',
                    style: AppTypography.bodyL.copyWith(
                      color: c.ink,
                      fontWeight: FontWeight.w600,
                      fontSize: 13,
                    ),
                  ),
                ),
                Icon(Icons.chevron_right, color: c.inkFaint, size: 20),
              ],
            ),
          ),
        ),
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
