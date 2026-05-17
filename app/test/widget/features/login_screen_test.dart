// Widget test Login screen — auth pakai mock BiometricHelper
// (in-memory, backend belum ada).

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:emas_berlian_insight/theme/app_theme.dart';
import 'package:emas_berlian_insight/utils/biometric_helper.dart';
import 'package:emas_berlian_insight/features/auth/application/auth_controller.dart';
import 'package:emas_berlian_insight/features/auth/presentation/login_screen.dart';
import 'package:emas_berlian_insight/features/auth/presentation/widgets/biometric_button.dart';

/// Mock helper — hasil biometric ditentukan test.
class _MockBiometric implements BiometricHelper {
  _MockBiometric(this._result, {this.available = true});

  final BiometricResult _result;
  final bool available;

  @override
  Future<bool> isAvailable() async => available;

  @override
  Future<BiometricResult> authenticate() async => _result;
}

Future<void> _pump(
  WidgetTester tester,
  BiometricHelper helper, {
  VoidCallback? onAuth,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        biometricHelperProvider.overrideWithValue(helper),
      ],
      child: MaterialApp(
        theme: AppTheme.darkTheme,
        home: LoginScreen(onAuthenticated: onAuth),
      ),
    ),
  );
  await tester.pump();
}

void main() {
  testWidgets('render brand + label + footer', (tester) async {
    await _pump(tester, _MockBiometric(BiometricResult.success));

    expect(find.text('Sentuh untuk masuk'), findsOneWidget);
    expect(find.text('Executive Business Intelligence'), findsOneWidget);
    expect(find.text('AKSES KHUSUS DIREKSI'), findsOneWidget);
    expect(find.byType(BiometricButton), findsOneWidget);
  });

  testWidgets('biometric sukses → onAuthenticated dipanggil',
      (tester) async {
    var authed = false;
    await _pump(
      tester,
      _MockBiometric(BiometricResult.success),
      onAuth: () => authed = true,
    );

    await tester.tap(find.byType(BiometricButton));
    await tester.pump(); // authenticating
    await tester.pump(const Duration(seconds: 1)); // mock login delay

    expect(authed, isTrue);
  });

  testWidgets('biometric unavailable → pesan error', (tester) async {
    await _pump(
      tester,
      _MockBiometric(BiometricResult.unavailable, available: false),
    );
    await tester.pump();

    expect(
      find.textContaining('Aktifkan Face ID'),
      findsOneWidget,
    );
  });

  testWidgets('biometric gagal → pesan gagal', (tester) async {
    await _pump(tester, _MockBiometric(BiometricResult.failed));

    await tester.tap(find.byType(BiometricButton));
    await tester.pump();
    await tester.pump();

    expect(find.textContaining('gagal'), findsOneWidget);
  });
}
