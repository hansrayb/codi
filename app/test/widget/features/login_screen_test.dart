// Widget test Login — mode dummy (tombol Masuk, biometric dinonaktifkan
// sementara; kode biometric tetap ada di controller).

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:emas_berlian_insight/theme/app_theme.dart';
import 'package:emas_berlian_insight/features/auth/presentation/login_screen.dart';
import 'package:emas_berlian_insight/widgets/emas_button.dart';

Future<void> _pump(
  WidgetTester tester, {
  VoidCallback? onAuth,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      child: MaterialApp(
        theme: AppTheme.lightTheme,
        darkTheme: AppTheme.darkTheme,
        home: LoginScreen(onAuthenticated: onAuth),
      ),
    ),
  );
  await tester.pump();
}

void main() {
  testWidgets('render brand + tombol Masuk + footer', (tester) async {
    await _pump(tester);

    expect(find.text('Executive Business Intelligence'), findsOneWidget);
    expect(find.text('Masuk'), findsOneWidget);
    expect(find.byType(EmasButton), findsOneWidget);
    expect(find.text('AKSES KHUSUS DIREKSI'), findsOneWidget);
  });

  testWidgets('tap Masuk → onAuthenticated dipanggil', (tester) async {
    var authed = false;
    await _pump(tester, onAuth: () => authed = true);

    await tester.tap(find.byType(EmasButton));
    await tester.pump(); // loggingIn
    await tester.pump(const Duration(milliseconds: 900)); // mock delay

    expect(authed, isTrue);
  });
}
