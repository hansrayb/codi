import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'features/auth/presentation/login_screen.dart';
import 'features/shell/presentation/app_shell.dart';
import 'providers/settings_store.dart';
import 'theme/app_theme.dart';

/// Root widget aplikasi.
///
/// MVP: theme light & dark (brand biru-cyan, ikut sistem) + Login →
/// `AppShell` (Beranda · Insight · Chat · placeholder), match
/// `docs/emas-berlian-insight.html`. Bottom nav fungsional via shell
/// `IndexedStack`. `go_router` penuh = Fase 2
/// (`docs/05-ARCHITECTURE.md`, `docs/07-ROADMAP.md`).
class EmasBerlianInsightApp extends ConsumerWidget {
  const EmasBerlianInsightApp({required this.onLogout, super.key});

  /// Dipanggil saat user logout — di-handle root (`AppBootstrap`) untuk
  /// me-recreate ProviderContainer (wipe seluruh state per-akun).
  final Future<void> Function() onLogout;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final themeMode = ref.watch(themeModeProvider);
    return MaterialApp(
      title: 'Emas Berlian Insight',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: themeMode,
      home: Builder(
        builder: (context) => LoginScreen(
          onAuthenticated: () => Navigator.of(context).pushReplacement(
            MaterialPageRoute<void>(
              builder: (_) => AppShell(onLogout: onLogout),
            ),
          ),
        ),
      ),
    );
  }
}
