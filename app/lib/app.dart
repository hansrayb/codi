import 'package:flutter/material.dart';

import 'features/auth/presentation/login_screen.dart';
import 'theme/app_theme.dart';

/// Root widget aplikasi.
///
/// Fase 1: theme dark-only + Login screen (match `docs/emas-berlian-insight.html`).
/// Routing `go_router` + Dashboard di-wire berikutnya
/// (`docs/05-ARCHITECTURE.md`, `docs/07-ROADMAP.md`). Sementara: login
/// sukses → placeholder Dashboard.
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
              builder: (_) => const _DashboardPlaceholder(),
            ),
          ),
        ),
      ),
    );
  }
}

/// Placeholder Dashboard — diganti DashboardScreen di Fase 1 Minggu 2.
class _DashboardPlaceholder extends StatelessWidget {
  const _DashboardPlaceholder();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Beranda', style: AppTypography.headlineM)),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.s24),
          child: Text(
            'Login berhasil.\nDashboard menyusul di tahap berikutnya.',
            textAlign: TextAlign.center,
            style: AppTypography.bodyL,
          ),
        ),
      ),
    );
  }
}
