import 'package:flutter/foundation.dart';

/// Mode UI Login (dual): email+password atau biometric tap.
/// `docs/06-SCREENS.md` S1 → Modes.
enum LoginMode {
  /// Form email + password (login pertama / fallback / biometric error).
  email,

  /// Tap biometric (device sudah enroll).
  biometric,
}

/// Status login sesuai `docs/06-SCREENS.md` (S1 → State).
enum LoginStatus {
  /// Screen baru di-load.
  initial,

  /// Sedang cek ketersediaan biometric.
  checking,

  /// Biometric tidak tersedia di device.
  unavailable,

  /// Prompt biometric aktif / submit email login.
  authenticating,

  /// Sedang panggil API login.
  loggingIn,

  /// Sedang enroll device fingerprint setelah email-login sukses.
  enrolling,

  /// Sukses — siap navigate ke dashboard.
  success,

  /// Gagal — tampilkan error.
  failed,

  /// Terlalu banyak gagal — locked sementara.
  locked,
}

/// State immutable untuk Login screen.
@immutable
class AuthState {
  const AuthState({
    this.mode = LoginMode.email,
    this.status = LoginStatus.initial,
    this.email = '',
    this.errorMessage,
    this.errorCode,
    this.scopes = const <String>[],
    this.hasEnrolledBiometric = false,
    this.biometricAvailable = false,
  });

  /// Mode UI aktif.
  final LoginMode mode;

  /// Status saat ini.
  final LoginStatus status;

  /// Email yang sedang diketik (controller tetap di-screen state).
  final String email;

  /// Pesan error ramah (saat [status] == failed/unavailable/locked).
  final String? errorMessage;

  /// Kode error API (untuk routing UX, mis. `device_not_enrolled`).
  final String? errorCode;

  /// Scope JWT user yang sudah login (dari `/auth/login` response).
  final List<String> scopes;

  /// Flag lokal per-device: sudah pernah enroll biometric?
  final bool hasEnrolledBiometric;

  /// Biometric hardware tersedia di device ini.
  final bool biometricAvailable;

  /// True kalau sedang proses (prompt biometric / login / enroll).
  bool get isBusy =>
      status == LoginStatus.authenticating ||
      status == LoginStatus.loggingIn ||
      status == LoginStatus.enrolling ||
      status == LoginStatus.checking;

  /// Boleh tap biometric? Hanya kalau mode biometric, hardware available,
  /// dan tak sedang busy/locked.
  bool get canUseBiometric =>
      mode == LoginMode.biometric &&
      biometricAvailable &&
      hasEnrolledBiometric &&
      status != LoginStatus.locked &&
      !isBusy;

  AuthState copyWith({
    LoginMode? mode,
    LoginStatus? status,
    String? email,
    String? errorMessage,
    String? errorCode,
    List<String>? scopes,
    bool? hasEnrolledBiometric,
    bool? biometricAvailable,
    bool clearError = false,
  }) {
    return AuthState(
      mode: mode ?? this.mode,
      status: status ?? this.status,
      email: email ?? this.email,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      errorCode: clearError ? null : (errorCode ?? this.errorCode),
      scopes: scopes ?? this.scopes,
      hasEnrolledBiometric: hasEnrolledBiometric ?? this.hasEnrolledBiometric,
      biometricAvailable: biometricAvailable ?? this.biometricAvailable,
    );
  }

  @override
  bool operator ==(Object other) =>
      other is AuthState &&
      other.mode == mode &&
      other.status == status &&
      other.email == email &&
      other.errorMessage == errorMessage &&
      other.errorCode == errorCode &&
      listEquals(other.scopes, scopes) &&
      other.hasEnrolledBiometric == hasEnrolledBiometric &&
      other.biometricAvailable == biometricAvailable;

  @override
  int get hashCode => Object.hash(
        mode,
        status,
        email,
        errorMessage,
        errorCode,
        Object.hashAll(scopes),
        hasEnrolledBiometric,
        biometricAvailable,
      );
}
