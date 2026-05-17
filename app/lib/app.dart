import 'package:flutter/material.dart';

/// Root widget aplikasi.
///
/// Scaffolding Fase 0 — `MaterialApp` minimal tanpa theme/router custom.
/// Theme (`docs/03-DESIGN-SYSTEM.md`) dan `go_router`
/// (`docs/05-ARCHITECTURE.md`) di-wire di Fase 1.
class EmasBerlianInsightApp extends StatelessWidget {
  const EmasBerlianInsightApp({super.key});

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(
      title: 'Emas Berlian Insight',
      debugShowCheckedModeBanner: false,
      home: _ScaffoldingPlaceholder(),
    );
  }
}

/// Placeholder sementara Fase 0 — diganti Login screen di Fase 1.
class _ScaffoldingPlaceholder extends StatelessWidget {
  const _ScaffoldingPlaceholder();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(
        child: Text('Emas Berlian Insight — scaffolding'),
      ),
    );
  }
}
