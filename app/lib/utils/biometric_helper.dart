import 'package:local_auth/local_auth.dart';

/// Hasil percobaan autentikasi biometric.
enum BiometricResult {
  /// Berhasil terotentikasi.
  success,

  /// User membatalkan (tidak dianggap error — lihat `docs/06-SCREENS.md`).
  cancelled,

  /// Biometric tidak tersedia / belum di-enroll di device.
  unavailable,

  /// Gagal otentikasi (sidik jari/wajah tidak cocok).
  failed,
}

/// Wrapper tipis di atas `local_auth`.
///
/// Hanya urus biometric device. "Login API" terpisah di controller
/// (saat ini stub in-memory — backend Codi belum ada endpoint).
class BiometricHelper {
  BiometricHelper({LocalAuthentication? auth})
      : _auth = auth ?? LocalAuthentication();

  final LocalAuthentication _auth;

  /// Cek device punya biometric yang bisa dipakai.
  Future<bool> isAvailable() async {
    try {
      final supported = await _auth.isDeviceSupported();
      final canCheck = await _auth.canCheckBiometrics;
      return supported && canCheck;
    } on Exception {
      return false;
    }
  }

  /// Trigger prompt biometric native.
  Future<BiometricResult> authenticate() async {
    try {
      final available = await isAvailable();
      if (!available) return BiometricResult.unavailable;

      final ok = await _auth.authenticate(
        localizedReason: 'Otentikasi untuk masuk ke Emas Berlian Insight',
        options: const AuthenticationOptions(
          biometricOnly: true,
          stickyAuth: true,
        ),
      );
      return ok ? BiometricResult.success : BiometricResult.failed;
    } on Exception {
      // local_auth lempar PlatformException untuk cancel/lockout/no-enroll.
      // Disederhanakan: anggap cancelled (UX: stay di screen, no error).
      return BiometricResult.cancelled;
    }
  }
}
