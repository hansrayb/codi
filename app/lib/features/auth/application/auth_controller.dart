import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api/api_exception.dart';
import '../../../api/repositories/auth_repository.dart';
import '../../../utils/biometric_helper.dart';
import '../domain/auth_state.dart';

/// Provider helper biometric (bisa di-override di test).
final biometricHelperProvider = Provider<BiometricHelper>((ref) {
  return BiometricHelper();
});

/// Controller Login.
///
/// **Mock auth in-memory** — backend Codi belum expose `/auth/login`
/// (lihat `docs/04-API-CONTRACT.md`, `docs/07-ROADMAP.md` Risk Register).
/// Token tidak disimpan ke secure storage dulu (keputusan: in-memory
/// sementara, di-wire saat API real ada).
class AuthController extends Notifier<AuthState> {
  static const int _maxAttempts = 5;
  int _failedAttempts = 0;

  @override
  AuthState build() => const AuthState();

  BiometricHelper get _biometric => ref.read(biometricHelperProvider);

  /// Cek ketersediaan biometric saat screen load.
  Future<void> checkAvailability() async {
    state = state.copyWith(status: LoginStatus.checking, clearError: true);
    final available = await _biometric.isAvailable();
    state = state.copyWith(
      status: available ? LoginStatus.initial : LoginStatus.unavailable,
      errorMessage: available
          ? null
          : 'Aktifkan Face ID / sidik jari di pengaturan perangkat.',
    );
  }

  /// Trigger biometric → (mock) login.
  Future<void> authenticate() async {
    if (state.status == LoginStatus.locked) return;

    state = state.copyWith(
      status: LoginStatus.authenticating,
      clearError: true,
    );

    final result = await _biometric.authenticate();

    switch (result) {
      case BiometricResult.cancelled:
        // UX: stay di screen, tanpa pesan error.
        state = state.copyWith(status: LoginStatus.initial);
      case BiometricResult.unavailable:
        state = state.copyWith(
          status: LoginStatus.unavailable,
          errorMessage:
              'Aktifkan Face ID / sidik jari di pengaturan perangkat.',
        );
      case BiometricResult.failed:
        _registerFailure();
      case BiometricResult.success:
        await _doLogin();
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

  /// Login dummy tanpa biometric (tombol "Masuk") — tetap panggil
  /// `/auth/login` nyata, hanya lewati prompt biometric.
  Future<void> loginDummy() async {
    if (state.isBusy) return;
    await _doLogin();
  }

  /// Panggil `POST /auth/login` via repository → simpan token → success.
  Future<void> _doLogin() async {
    state = state.copyWith(status: LoginStatus.loggingIn, clearError: true);
    try {
      await ref.read(authRepositoryProvider).login(
            deviceId: 'emas-berlian-insight-device',
            platform: 'android',
          );
      _failedAttempts = 0;
      state = state.copyWith(status: LoginStatus.success);
    } on ApiException catch (e) {
      state = state.copyWith(status: LoginStatus.failed, errorMessage: e.message);
    }
  }
}

/// Provider state Login.
final authControllerProvider =
    NotifierProvider<AuthController, AuthState>(AuthController.new);
