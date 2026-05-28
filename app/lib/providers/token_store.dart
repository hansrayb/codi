import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Penyimpanan token JWT di Keychain (iOS) / Keystore (Android) via
/// `flutter_secure_storage` (`docs/02-SPEC.md` → Privacy & Security).
///
/// Token + refresh + scopes + role + flag biometric enrollment.
/// Token juga di-cache in-memory agar interceptor sinkron.
class TokenStore {
  TokenStore(this._storage);

  static const _kAccess = 'access_token';
  static const _kRefresh = 'refresh_token';
  static const _kScopes = 'scopes';
  static const _kRole = 'role_slug';
  static const _kEmail = 'email';
  static const _kAccountId = 'account_id';
  static const _kName = 'name';
  static const _kTitle = 'title';
  static const _kEnrolled = 'biometric_enrolled';

  final FlutterSecureStorage _storage;
  String? _accessCache;
  List<String> _scopesCache = const <String>[];
  String _roleCache = '';
  String _emailCache = '';
  String _accountIdCache = '';
  String _nameCache = '';
  String _titleCache = '';
  bool _enrolledCache = false;

  /// Token akses saat ini (sinkron, dari cache memory).
  String? get accessToken => _accessCache;

  /// Scope JWT user terakhir login.
  List<String> get scopes => _scopesCache;

  /// Role slug user (superadmin/admin/director/viewer).
  String get role => _roleCache;

  /// Email user.
  String get email => _emailCache;

  /// Account ID user.
  String get accountId => _accountIdCache;

  /// Nama lengkap user.
  String get name => _nameCache;

  /// Jabatan user.
  String get title => _titleCache;

  /// Flag lokal: device sudah enroll biometric?
  bool get hasEnrolledBiometric => _enrolledCache;

  /// Muat token + scopes + flag tersimpan ke cache (panggil saat bootstrap).
  Future<void> load() async {
    _accessCache = await _storage.read(key: _kAccess);
    final scopesRaw = await _storage.read(key: _kScopes);
    _scopesCache = (scopesRaw ?? '').split(',').where((s) => s.isNotEmpty).toList();
    _roleCache = (await _storage.read(key: _kRole)) ?? '';
    _emailCache = (await _storage.read(key: _kEmail)) ?? '';
    _accountIdCache = (await _storage.read(key: _kAccountId)) ?? '';
    _nameCache = (await _storage.read(key: _kName)) ?? '';
    _titleCache = (await _storage.read(key: _kTitle)) ?? '';
    _enrolledCache = (await _storage.read(key: _kEnrolled)) == '1';
  }

  /// Simpan hasil login.
  Future<void> saveSession({
    required String accessToken,
    String? refreshToken,
    List<String>? scopes,
    String? role,
    String? email,
    String? accountId,
    String? name,
    String? title,
  }) async {
    _accessCache = accessToken;
    if (scopes != null) _scopesCache = scopes;
    if (role != null) _roleCache = role;
    if (email != null) _emailCache = email;
    if (accountId != null) _accountIdCache = accountId;
    if (name != null) _nameCache = name;
    if (title != null) _titleCache = title;
    await _storage.write(key: _kAccess, value: accessToken);
    if (refreshToken != null) {
      await _storage.write(key: _kRefresh, value: refreshToken);
    }
    if (scopes != null) {
      await _storage.write(key: _kScopes, value: scopes.join(','));
    }
    if (role != null) {
      await _storage.write(key: _kRole, value: role);
    }
    if (email != null) {
      await _storage.write(key: _kEmail, value: email);
    }
    if (accountId != null) {
      await _storage.write(key: _kAccountId, value: accountId);
    }
    if (name != null) {
      await _storage.write(key: _kName, value: name);
    }
    if (title != null) {
      await _storage.write(key: _kTitle, value: title);
    }
  }

  /// Hanya simpan token (fallback bootstrap token Fase A1).
  Future<void> save({
    required String accessToken,
    String? refreshToken,
  }) =>
      saveSession(accessToken: accessToken, refreshToken: refreshToken);

  /// Tandai device sudah enroll biometric.
  Future<void> setEnrolled(bool value) async {
    _enrolledCache = value;
    await _storage.write(key: _kEnrolled, value: value ? '1' : '0');
  }

  Future<void> clear() async {
    _accessCache = null;
    _scopesCache = const <String>[];
    _roleCache = '';
    _emailCache = '';
    _accountIdCache = '';
    _nameCache = '';
    _titleCache = '';
    // hasEnrolledBiometric DIPERTAHANKAN — supaya logout tidak mereset
    // enrollment device. User tetap bisa login biometric setelah logout.
    await _storage.delete(key: _kAccess);
    await _storage.delete(key: _kRefresh);
    await _storage.delete(key: _kScopes);
    await _storage.delete(key: _kRole);
    await _storage.delete(key: _kEmail);
    await _storage.delete(key: _kAccountId);
    await _storage.delete(key: _kName);
    await _storage.delete(key: _kTitle);
  }

  /// Hapus juga flag enrollment (saat backend balas `device_not_enrolled`).
  Future<void> clearEnrollment() async {
    _enrolledCache = false;
    await _storage.delete(key: _kEnrolled);
  }

  bool get hasToken => (_accessCache ?? '').isNotEmpty;

  /// Cek scope tertentu (untuk UI gating).
  bool hasScope(String scope) => _scopesCache.contains(scope);
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
