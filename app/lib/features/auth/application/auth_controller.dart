import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api/api_exception.dart';
import '../../../api/repositories/auth_repository.dart';
import '../../../providers/device_id_store.dart';
import '../../../providers/token_store.dart';
import '../../../utils/biometric_helper.dart';
import '../domain/auth_state.dart';

/// Provider helper biometric (bisa di-override di test).
final biometricHelperProvider = Provider<BiometricHelper>((ref) {
  return BiometricHelper();
});

/// Controller Login dual-mode (`docs/06-SCREENS.md` S1).
///
/// Mode email: form email + password → `POST /auth/login` → auto-enroll
/// device fingerprint → success. Mode biometric: tap → local prompt →
/// `POST /auth/login-biometric` (device sudah enroll).
class AuthController extends Notifier<AuthState> {
  static const int _maxAttempts = 5;
  int _failedAttempts = 0;

  @override
  AuthState build() {
    final store = ref.read(tokenStoreProvider);
    final hasEnrolled = store.hasEnrolledBiometric;
    return AuthState(
      mode: hasEnrolled ? LoginMode.biometric : LoginMode.email,
      hasEnrolledBiometric: hasEnrolled,
      email: store.email,
    );
  }

  BiometricHelper get _biometric => ref.read(biometricHelperProvider);
  AuthRepository get _repo => ref.read(authRepositoryProvider);
  DeviceIdStore get _device => ref.read(deviceIdStoreProvider);
  TokenStore get _tokenStore => ref.read(tokenStoreProvider);

  /// Cek ketersediaan biometric saat screen load. Kalau tak available,
  /// paksa Mode email.
  Future<void> checkAvailability() async {
    state = state.copyWith(status: LoginStatus.checking, clearError: true);
    final available = await _biometric.isAvailable();
    final mode = (available && state.hasEnrolledBiometric)
        ? LoginMode.biometric
        : LoginMode.email;
    state = state.copyWith(
      status: LoginStatus.initial,
      biometricAvailable: available,
      mode: mode,
    );
  }

  /// Switch UI manual antara form email & biometric.
  void switchMode(LoginMode mode) {
    if (state.isBusy) return;
    state = state.copyWith(mode: mode, clearError: true);
  }

  /// Update email field (controller di screen state).
  void setEmail(String value) {
    state = state.copyWith(email: value);
  }

  /// Submit form email + password.
  Future<void> loginEmail({required String password}) async {
    if (state.status == LoginStatus.locked) return;
    final email = state.email.trim();
    if (email.isEmpty || !email.contains('@')) {
      state = state.copyWith(
        status: LoginStatus.failed,
        errorMessage: 'Email tidak valid.',
        errorCode: 'invalid_payload',
      );
      return;
    }
    if (password.isEmpty) {
      state = state.copyWith(
        status: LoginStatus.failed,
        errorMessage: 'Password wajib diisi.',
        errorCode: 'invalid_payload',
      );
      return;
    }
    state = state.copyWith(status: LoginStatus.loggingIn, clearError: true);
    try {
      final result = await _repo.loginEmail(email: email, password: password);
      _failedAttempts = 0;
      state = state.copyWith(
        scopes: result.scopes,
        clearError: true,
      );
      await _tryEnrollAfterLogin();
      state = state.copyWith(status: LoginStatus.success);
    } on ApiException catch (e) {
      _registerApiFailure(e);
    }
  }

  /// Trigger biometric → API login-biometric.
  Future<void> loginBiometric() async {
    if (state.status == LoginStatus.locked) return;
    if (!state.canUseBiometric) return;

    state = state.copyWith(status: LoginStatus.authenticating, clearError: true);
    final result = await _biometric.authenticate();
    switch (result) {
      case BiometricResult.cancelled:
        state = state.copyWith(status: LoginStatus.initial);
        return;
      case BiometricResult.unavailable:
        state = state.copyWith(
          status: LoginStatus.initial,
          mode: LoginMode.email,
          biometricAvailable: false,
          errorMessage: 'Aktifkan Face ID / sidik jari di pengaturan perangkat.',
        );
        return;
      case BiometricResult.failed:
        _registerFailure();
        return;
      case BiometricResult.success:
        break;
    }
    await _doLoginBiometric();
  }

  Future<void> _doLoginBiometric() async {
    state = state.copyWith(status: LoginStatus.loggingIn, clearError: true);
    try {
      final res = await _repo.loginBiometric(
        deviceId: _device.deviceId,
        deviceFingerprint: _device.fingerprint,
      );
      _failedAttempts = 0;
      state = state.copyWith(
        scopes: res.scopes,
        status: LoginStatus.success,
        clearError: true,
      );
    } on ApiException catch (e) {
      if (e.statusCode == 401) {
        // Device tak dikenal lagi (mis. di-revoke server) → reset enrollment,
        // paksa user login email.
        await _tokenStore.clearEnrollment();
        state = state.copyWith(
          mode: LoginMode.email,
          hasEnrolledBiometric: false,
          status: LoginStatus.failed,
          errorMessage: 'Sesi biometric tidak berlaku. Silakan login email.',
          errorCode: 'device_not_enrolled',
        );
        return;
      }
      _registerApiFailure(e);
    }
  }

  /// Auto-enroll device setelah login email pertama. Idempotent — kalau
  /// gagal, abaikan (user tetap login, biometric tinggal dicoba lagi nanti).
  Future<void> _tryEnrollAfterLogin() async {
    state = state.copyWith(status: LoginStatus.enrolling);
    try {
      await _repo.enrollBiometric(
        deviceId: _device.deviceId,
        deviceFingerprint: _device.fingerprint,
        platform: _device.platform,
      );
      await _tokenStore.setEnrolled(true);
      state = state.copyWith(hasEnrolledBiometric: true);
    } on ApiException {
      // Enrollment opsional; kalau gagal, biarkan user pakai email saja.
    }
  }

  void _registerFailure() {
    _failedAttempts++;
    if (_failedAttempts >= _maxAttempts) {
      state = state.copyWith(
        status: LoginStatus.locked,
        errorMessage:
            'Terlalu banyak percobaan gagal. Coba lagi dalam 5 menit.',
      );
    } else {
      state = state.copyWith(
        status: LoginStatus.failed,
        errorMessage: 'Otentikasi gagal. Silakan coba lagi.',
      );
    }
  }

  void _registerApiFailure(ApiException e) {
    if (e.statusCode == 429) {
      state = state.copyWith(
        status: LoginStatus.locked,
        errorMessage: e.message,
        errorCode: 'too_many_attempts',
      );
      return;
    }
    state = state.copyWith(
      status: LoginStatus.failed,
      errorMessage: e.message,
      errorCode: e.statusCode == 401 ? 'invalid_credentials' : null,
    );
  }
}

/// Provider state Login.
final authControllerProvider =
    NotifierProvider<AuthController, AuthState>(AuthController.new);
