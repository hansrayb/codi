import 'package:flutter/material.dart';

import 'features/auth/presentation/login_screen.dart';
import 'features/chat/presentation/chat_screen.dart';
import 'features/dashboard/presentation/dashboard_screen.dart';
import 'theme/app_theme.dart';

/// Root widget aplikasi.
///
/// Fase 1: theme light & dark (brand biru-cyan, ikut sistem) + Login +
/// Dashboard + Chat (match `docs/emas-berlian-insight.html`). Routing
/// `go_router` di-wire berikutnya (`docs/05-ARCHITECTURE.md`).
/// Sementara: Navigator manual. Insight (S4) belum ada.
class EmasBerlianInsightApp extends StatelessWidget {
  const EmasBerlianInsightApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Emas Berlian Insight',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: ThemeMode.system,
      home: Builder(
        builder: (context) => LoginScreen(
          onAuthenticated: () => Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (dashCtx) => DashboardScreen(
                onOpenChat: () => Navigator.of(dashCtx).push(
                  MaterialPageRoute<void>(
                    builder: (_) => const ChatScreen(),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
