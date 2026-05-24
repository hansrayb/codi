/// Environment config (`docs/05-ARCHITECTURE.md` → Environment Configuration).
///
/// Pilih via `--dart-define=ENV=dev|staging|prod`. Base URL bisa
/// di-override eksplisit `--dart-define=API_BASE_URL=...` (mis. saat tes
/// di HP fisik, localhost backend tak terjangkau — pakai IP LAN laptop:
/// `flutter run --dart-define=API_BASE_URL=http://192.168.x.x:8787/api/v1`).
abstract final class Env {
  const Env._();

  static const String env =
      String.fromEnvironment('ENV', defaultValue: 'dev');

  static const String _override =
      String.fromEnvironment('API_BASE_URL', defaultValue: '');

  /// Base URL backend Codi (`/api/v1`).
  static String get apiBaseUrl {
    if (_override.isNotEmpty) return _override;
    switch (env) {
      case 'prod':
        return 'https://codi.lumbungemas.internal/api/v1';
      case 'staging':
        return 'https://staging.codi.lumbungemas.internal/api/v1';
      default:
        return 'http://localhost:8787/api/v1';
    }
  }

  /// Token akses awal stub (Fase A1 shared-token). Saat backend punya
  /// login nyata, ini kosong dan token didapat dari `/auth/login`.
  static const String bootstrapToken =
      String.fromEnvironment('CODI_SHARED_TOKEN', defaultValue: '');

  static bool get isProduction => env == 'prod';
  static bool get enableLogging => !isProduction;

  /// Header wajib (`docs/04-API-CONTRACT.md`).
  static Map<String, String> get clientHeaders => const {
        'X-Client': 'emas-berlian-insight',
        'X-Client-Version': '1.0.0',
        'Accept': 'application/json',
      };
}
