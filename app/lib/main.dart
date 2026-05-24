import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'api/repositories/auth_repository.dart';
import 'app.dart';
import 'providers/token_store.dart';

/// Entry point Emas Berlian Insight.
void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initializeDateFormatting('id_ID');

  // Container dibuat lebih awal agar token tersimpan dimuat sebelum frame
  // pertama (interceptor butuh token sinkron).
  final container = ProviderContainer();
  final tokenStore = container.read(tokenStoreProvider);
  await tokenStore.load();
  await applyBootstrapToken(tokenStore);

  runApp(
    UncontrolledProviderScope(
      container: container,
      child: const EmasBerlianInsightApp(),
    ),
  );
}
