import 'dart:convert';
import 'dart:io' show Platform;
import 'dart:math';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'token_store.dart';

/// Identitas device untuk binding biometric ke akun di server
/// (`/auth/enroll-biometric` + `/auth/login-biometric`).
///
/// Generate sekali saat first launch, persist di secure storage.
/// Fingerprint != device_id agar server bisa verify ulang.
class DeviceIdStore {
  DeviceIdStore(this._storage);

  static const _kDeviceId = 'codi_device_id';
  static const _kFingerprint = 'codi_device_fingerprint';

  final FlutterSecureStorage _storage;
  String? _deviceIdCache;
  String? _fingerprintCache;

  String get deviceId => _deviceIdCache ?? '';
  String get fingerprint => _fingerprintCache ?? '';

  String get platform {
    if (Platform.isAndroid) return 'android';
    if (Platform.isIOS) return 'ios';
    return 'unknown';
  }

  Future<void> load() async {
    _deviceIdCache = await _storage.read(key: _kDeviceId);
    _fingerprintCache = await _storage.read(key: _kFingerprint);
    if ((_deviceIdCache ?? '').isEmpty) {
      _deviceIdCache = '$platform-${_randomHex(8)}';
      await _storage.write(key: _kDeviceId, value: _deviceIdCache);
    }
    if ((_fingerprintCache ?? '').isEmpty) {
      _fingerprintCache = 'sha256:${_randomHex(32)}';
      await _storage.write(key: _kFingerprint, value: _fingerprintCache);
    }
  }

  static String _randomHex(int bytes) {
    final r = Random.secure();
    final buf = List<int>.generate(bytes, (_) => r.nextInt(256));
    return base64Url.encode(buf).replaceAll('=', '').toLowerCase();
  }
}

final deviceIdStoreProvider = Provider<DeviceIdStore>((ref) {
  return DeviceIdStore(ref.read(secureStorageProvider));
});
