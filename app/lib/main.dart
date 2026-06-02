import 'package:flutter/material.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'app_bootstrap.dart';

/// Entry point Emas Berlian Insight.
void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initializeDateFormatting('id_ID');

  // Container dibuat lebih awal agar token tersimpan dimuat sebelum frame
  // pertama (interceptor butuh token sinkron). Bootstrap token hanya
  // di-apply pada cold start.
  final container = await createAppContainer(applyBootstrap: true);

  runApp(AppBootstrap(initialContainer: container));
}
