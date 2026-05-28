// Widget test Login dual-mode — repository + biometric helper + token store
// + device_id store di-override fake (tanpa HTTP/secure storage real).

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:emas_berlian_insight/api/api_exception.dart';
import 'package:emas_berlian_insight/api/repositories/auth_repository.dart';
import 'package:emas_berlian_insight/features/auth/application/auth_controller.dart';
import 'package:emas_berlian_insight/features/auth/presentation/login_screen.dart';
import 'package:emas_berlian_insight/features/auth/presentation/widgets/biometric_button.dart';
import 'package:emas_berlian_insight/providers/device_id_store.dart';
import 'package:emas_berlian_insight/providers/token_store.dart';
import 'package:emas_berlian_insight/theme/app_theme.dart';
import 'package:emas_berlian_insight/utils/biometric_helper.dart';
import 'package:emas_berlian_insight/widgets/emas_button.dart';

class _FakeAuthRepo implements AuthRepository {
  _FakeAuthRepo({this.shouldFailLogin = false});

  bool shouldFailLogin;
  bool loginEmailCalled = false;
  bool enrollCalled = false;
  bool loginBiometricCalled = false;

  @override
  Future<AuthLoginResult> loginEmail({
    required String email,
    required String password,
  }) async {
    loginEmailCalled = true;
    if (shouldFailLogin) {
      throw const ApiException(
        kind: ApiErrorKind.unauthorized,
        message: 'Email atau password salah.',
        statusCode: 401,
      );
    }
    return const AuthLoginResult(
      accountId: 'acc_test',
      email: 'hans@emasberlian.com',
      name: 'Hans',
      title: 'Super Admin',
      role: 'superadmin',
      scopes: ['accounts:read', 'dashboard:read'],
    );
  }

  @override
  Future<AuthLoginResult> loginBiometric({
    required String deviceId,
    required String deviceFingerprint,
  }) async {
    loginBiometricCalled = true;
    return const AuthLoginResult(
      accountId: 'acc_test',
      email: 'hans@emasberlian.com',
      name: 'Hans',
      title: 'Super Admin',
      role: 'superadmin',
      scopes: ['accounts:read', 'dashboard:read'],
    );
  }

  @override
  Future<void> enrollBiometric({
    required String deviceId,
    required String deviceFingerprint,
    required String platform,
  }) async {
    enrollCalled = true;
  }

  @override
  Future<AuthLoginResult> refresh(String refreshToken) async =>
      throw UnimplementedError();

  @override
  Future<void> logout() async {}
}

class _FakeBiometricHelper implements BiometricHelper {
  _FakeBiometricHelper({
    this.result = BiometricResult.success,
  });

  final BiometricResult result;

  @override
  Future<bool> isAvailable() async => true;

  @override
  Future<BiometricResult> authenticate() async => result;
}

class _FakeDeviceIdStore implements DeviceIdStore {
  @override
  String get deviceId => 'android-test-1';

  @override
  String get fingerprint => 'sha256:test';

  @override
  String get platform => 'android';

  @override
  Future<void> load() async {}
}

class _FakeTokenStore implements TokenStore {
  _FakeTokenStore({this.enrolled = false, String email = ''}) : _email = email;

  bool enrolled;
  String _email;

  @override
  String? get accessToken => null;
  @override
  List<String> get scopes => const [];
  @override
  String get role => '';
  @override
  String get email => _email;
  @override
  String get accountId => '';
  @override
  bool get hasEnrolledBiometric => enrolled;
  @override
  bool get hasToken => false;

  @override
  Future<void> load() async {}

  @override
  Future<void> save({required String accessToken, String? refreshToken}) async {}

  @override
  Future<void> saveSession({
    required String accessToken,
    String? refreshToken,
    List<String>? scopes,
    String? role,
    String? email,
    String? accountId,
  }) async {}

  @override
  Future<void> setEnrolled(bool value) async {
    enrolled = value;
  }

  @override
  Future<void> clear() async {}

  @override
  Future<void> clearEnrollment() async {
    enrolled = false;
  }

  @override
  bool hasScope(String scope) => false;
}

Future<void> _pump(
  WidgetTester tester, {
  required _FakeAuthRepo repo,
  required _FakeBiometricHelper biometric,
  _FakeTokenStore? tokenStore,
  VoidCallback? onAuth,
}) async {
  final store = tokenStore ?? _FakeTokenStore();
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        authRepositoryProvider.overrideWithValue(repo),
        biometricHelperProvider.overrideWithValue(biometric),
        tokenStoreProvider.overrideWithValue(store),
        deviceIdStoreProvider.overrideWithValue(_FakeDeviceIdStore()),
      ],
      child: MaterialApp(
        theme: AppTheme.lightTheme,
        darkTheme: AppTheme.darkTheme,
        home: LoginScreen(onAuthenticated: onAuth),
      ),
    ),
  );
  await _settle(tester);
}

/// Pump beberapa frame manual. `pumpAndSettle` tak bisa dipakai karena
/// `BiometricButton` punya pulse animation infinite (timeout 10 detik).
Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 8; i++) {
    await tester.pump(const Duration(milliseconds: 100));
  }
}

void main() {
  testWidgets('default mode = email (belum enroll) → render form Masuk',
      (tester) async {
    await _pump(
      tester,
      repo: _FakeAuthRepo(),
      biometric: _FakeBiometricHelper(),
    );
    expect(find.text('Masuk'), findsOneWidget);
    expect(find.text('Executive Business Intelligence'), findsOneWidget);
    expect(find.text('AKSES KHUSUS DIREKSI'), findsOneWidget);
    // Belum enroll → tak ada link "Pakai biometric".
    expect(find.text('Pakai biometric'), findsNothing);
  });

  testWidgets('login email sukses → onAuthenticated + enroll dipanggil',
      (tester) async {
    final repo = _FakeAuthRepo();
    var authed = false;
    await _pump(
      tester,
      repo: repo,
      biometric: _FakeBiometricHelper(),
      onAuth: () => authed = true,
    );
    await tester.enterText(find.byType(TextField).first, 'hans@emasberlian.com');
    await tester.enterText(find.byType(TextField).last, 'Sup3rPa55!');
    await tester.tap(find.byType(EmasButton));
    await _settle(tester);
    expect(repo.loginEmailCalled, isTrue);
    expect(repo.enrollCalled, isTrue);
    expect(authed, isTrue);
  });

  testWidgets('login email gagal 401 → tampilkan pesan error', (tester) async {
    final repo = _FakeAuthRepo(shouldFailLogin: true);
    await _pump(
      tester,
      repo: repo,
      biometric: _FakeBiometricHelper(),
    );
    await tester.enterText(find.byType(TextField).first, 'hans@emasberlian.com');
    await tester.enterText(find.byType(TextField).last, 'wrong');
    await tester.tap(find.byType(EmasButton));
    await _settle(tester);
    expect(find.text('Email atau password salah.'), findsOneWidget);
  });

  testWidgets('email invalid → tak panggil API, tampil error inline',
      (tester) async {
    final repo = _FakeAuthRepo();
    await _pump(
      tester,
      repo: repo,
      biometric: _FakeBiometricHelper(),
    );
    await tester.enterText(find.byType(TextField).first, 'bukan-email');
    await tester.enterText(find.byType(TextField).last, 'apapun');
    await tester.tap(find.byType(EmasButton));
    await _settle(tester);
    expect(repo.loginEmailCalled, isFalse);
    expect(find.text('Email tidak valid.'), findsOneWidget);
  });

  testWidgets('sudah enroll + biometric available → default mode biometric',
      (tester) async {
    await _pump(
      tester,
      repo: _FakeAuthRepo(),
      biometric: _FakeBiometricHelper(),
      tokenStore: _FakeTokenStore(enrolled: true),
    );
    expect(find.text('Sentuh untuk masuk'), findsOneWidget);
    expect(find.text('Pakai email'), findsOneWidget);
  });

  testWidgets('tap biometric sukses → login-biometric dipanggil',
      (tester) async {
    final repo = _FakeAuthRepo();
    var authed = false;
    await _pump(
      tester,
      repo: repo,
      biometric: _FakeBiometricHelper(result: BiometricResult.success),
      tokenStore: _FakeTokenStore(enrolled: true),
      onAuth: () => authed = true,
    );
    await tester.tap(find.byType(BiometricButton));
    await _settle(tester);
    expect(repo.loginBiometricCalled, isTrue);
    expect(authed, isTrue);
  });

  testWidgets('switch mode email ↔ biometric (kalau enrolled)', (tester) async {
    await _pump(
      tester,
      repo: _FakeAuthRepo(),
      biometric: _FakeBiometricHelper(),
      tokenStore: _FakeTokenStore(enrolled: true),
    );
    // Default biometric → tap "Pakai email" → form muncul.
    await tester.tap(find.text('Pakai email'));
    await _settle(tester);
    expect(find.text('Masuk'), findsOneWidget);
    expect(find.text('Pakai biometric'), findsOneWidget);
    // Balik ke biometric.
    await tester.tap(find.text('Pakai biometric'));
    await _settle(tester);
    expect(find.text('Sentuh untuk masuk'), findsOneWidget);
  });
}
