import 'package:flutter/foundation.dart';

/// Status login sesuai `docs/06-SCREENS.md` (S1 → State).
enum LoginStatus {
  /// Screen baru di-load.
  initial,

  /// Sedang cek ketersediaan biometric.
  checking,

  /// Biometric tidak tersedia di device.
  unavailable,

  /// Prompt biometric aktif.
  authenticating,

  /// Sedang panggil "API" login (stub).
  loggingIn,

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
    this.status = LoginStatus.initial,
    this.errorMessage,
  });

  /// Status saat ini.
  final LoginStatus status;

  /// Pesan error ramah (saat [status] == failed/unavailable/locked).
  final String? errorMessage;

  /// True kalau sedang proses (prompt biometric atau login).
  bool get isBusy =>
      status == LoginStatus.authenticating ||
      status == LoginStatus.loggingIn ||
      status == LoginStatus.checking;

  AuthState copyWith({
    LoginStatus? status,
    String? errorMessage,
    bool clearError = false,
  }) {
    return AuthState(
      status: status ?? this.status,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
    );
  }

  @override
  bool operator ==(Object other) =>
      other is AuthState &&
      other.status == status &&
      other.errorMessage == errorMessage;

  @override
  int get hashCode => Object.hash(status, errorMessage);
}
