// Widget test Login — mode dummy (tombol Masuk). authRepository
// di-override fake (tanpa HTTP).

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:emas_berlian_insight/theme/app_theme.dart';
import 'package:emas_berlian_insight/api/repositories/auth_repository.dart';
import 'package:emas_berlian_insight/features/auth/presentation/login_screen.dart';
import 'package:emas_berlian_insight/widgets/emas_button.dart';

class _FakeAuthRepo implements AuthRepository {
  @override
  Future<void> login({
    required String deviceId,
    required String platform,
  }) async {}

  @override
  Future<void> logout() async {}
}

Future<void> _pump(
  WidgetTester tester, {
  VoidCallback? onAuth,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        authRepositoryProvider.overrideWithValue(_FakeAuthRepo()),
      ],
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
    await tester.pump(); // login future resolves
    await tester.pump(const Duration(milliseconds: 16));

    expect(authed, isTrue);
  });
}
