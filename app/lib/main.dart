import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'app.dart';

/// Entry point Emas Berlian Insight.
void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Wajib sebelum DateFormat locale id_ID dipakai (DateFormatter).
  await initializeDateFormatting('id_ID');
  runApp(
    const ProviderScope(
      child: EmasBerlianInsightApp(),
    ),
  );
}
