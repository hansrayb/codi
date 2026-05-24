import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Penyimpanan token JWT di Keychain (iOS) / Keystore (Android) via
/// `flutter_secure_storage` (`docs/02-SPEC.md` → Privacy & Security).
///
/// Token juga di-cache in-memory agar interceptor sinkron (tak perlu
/// await tiap request).
class TokenStore {
  TokenStore(this._storage);

  static const _kAccess = 'access_token';
  static const _kRefresh = 'refresh_token';

  final FlutterSecureStorage _storage;
  String? _accessCache;

  /// Token akses saat ini (sinkron, dari cache memory).
  String? get accessToken => _accessCache;

  /// Muat token tersimpan ke cache (panggil saat bootstrap).
  Future<void> load() async {
    _accessCache = await _storage.read(key: _kAccess);
  }

  Future<void> save({
    required String accessToken,
    String? refreshToken,
  }) async {
    _accessCache = accessToken;
    await _storage.write(key: _kAccess, value: accessToken);
    if (refreshToken != null) {
      await _storage.write(key: _kRefresh, value: refreshToken);
    }
  }

  Future<void> clear() async {
    _accessCache = null;
    await _storage.delete(key: _kAccess);
    await _storage.delete(key: _kRefresh);
  }

  bool get hasToken => (_accessCache ?? '').isNotEmpty;
}

/// Instance secure storage.
final secureStorageProvider = Provider<FlutterSecureStorage>((ref) {
  return const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );
});

/// Token store global.
final tokenStoreProvider = Provider<TokenStore>((ref) {
  return TokenStore(ref.read(secureStorageProvider));
});
