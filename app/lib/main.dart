import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';

/// Entry point Emas Berlian Insight.
///
/// Scaffolding Fase 0 — belum ada bootstrap logic (env, secure storage,
/// error handler). Itu ditambahkan di Fase 1 sesuai `docs/07-ROADMAP.md`.
void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(
    const ProviderScope(
      child: EmasBerlianInsightApp(),
    ),
  );
}
