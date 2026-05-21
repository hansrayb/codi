// Smoke test — pastikan app boot tanpa crash.
// Test per-fitur ada di test/widget/features/.

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:emas_berlian_insight/app.dart';
import 'package:emas_berlian_insight/features/auth/presentation/login_screen.dart';

void main() {
  testWidgets('App boot ke Login screen', (WidgetTester tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: EmasBerlianInsightApp(),
      ),
    );
    await tester.pump();

    expect(find.byType(LoginScreen), findsOneWidget);
  });
}
