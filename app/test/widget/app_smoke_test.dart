// Smoke test scaffolding Fase 0.
//
// Hanya memastikan app boot tanpa crash. Test per-fitur ditambahkan
// di Fase 1+ sesuai `docs/08-TESTING.md`.

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:emas_berlian_insight/app.dart';

void main() {
  testWidgets('App boot tanpa crash', (WidgetTester tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: EmasBerlianInsightApp(),
      ),
    );

    expect(find.text('Emas Berlian Insight — scaffolding'), findsOneWidget);
  });
}
