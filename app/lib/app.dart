import 'package:flutter/material.dart';

import 'features/auth/presentation/login_screen.dart';
import 'features/dashboard/presentation/dashboard_screen.dart';
import 'theme/app_theme.dart';

/// Root widget aplikasi.
///
/// Fase 1: theme dark-only + Login + Dashboard (match
/// `docs/emas-berlian-insight.html`). Routing `go_router` di-wire
/// berikutnya (`docs/05-ARCHITECTURE.md`). Sementara: Navigator manual,
/// Chat/Insight belum ada → snackbar placeholder.
class EmasBerlianInsightApp extends StatelessWidget {
  const EmasBerlianInsightApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Emas Berlian Insight',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      home: Builder(
        builder: (context) => LoginScreen(
          onAuthenticated: () => Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) => const DashboardScreen(),
            ),
          ),
        ),
      ),
    );
  }
}
