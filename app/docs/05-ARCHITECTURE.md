# 05 — ARCHITECTURE.md

Folder structure, state management, dan technical architecture untuk Emas Berlian Insight Flutter app.

---

## Folder Structure

```
apps/emas-berlian-insight/
├── docs/                              # Project documentation
│   ├── README.md
│   ├── 01-CLAUDE.md
│   └── ... (8 file md)
│
├── android/                           # Android native (generated)
├── ios/                               # iOS native (generated)
├── assets/
│   ├── fonts/                         # Optional: bundled fonts (kalau tidak pakai google_fonts)
│   ├── images/                        # PNG/JPG
│   ├── svg/                           # SVG icons & logo
│   │   ├── logo.svg
│   │   ├── codi_avatar.svg
│   │   └── ...
│   └── lottie/                        # Optional: lottie animations
│
├── lib/
│   ├── main.dart                      # Entry point
│   ├── app.dart                       # MaterialApp + theme + router
│   │
│   ├── config/                        # Configuration
│   │   ├── env.dart                   # Environment (dev/staging/prod)
│   │   ├── constants.dart             # App-wide constants
│   │   └── flavors.dart               # Flavor setup
│   │
│   ├── theme/                         # Design system implementation
│   │   ├── app_theme.dart             # ThemeData
│   │   ├── app_colors.dart            # Color tokens
│   │   ├── app_typography.dart        # Text styles
│   │   ├── app_spacing.dart           # Spacing tokens
│   │   ├── app_radius.dart            # Radius tokens
│   │   └── app_elevation.dart         # Shadow tokens
│   │
│   ├── routing/                       # go_router setup
│   │   ├── app_router.dart            # Router config
│   │   ├── route_paths.dart           # Route constants
│   │   └── guards/
│   │       └── auth_guard.dart        # Redirect if not authenticated
│   │
│   ├── api/                           # API layer
│   │   ├── api_client.dart            # Dio instance
│   │   ├── api_endpoints.dart
│   │   ├── api_exception.dart
│   │   ├── interceptors/
│   │   │   ├── auth_interceptor.dart
│   │   │   ├── logging_interceptor.dart
│   │   │   └── retry_interceptor.dart
│   │   └── repositories/
│   │       ├── auth_repository.dart
│   │       ├── dashboard_repository.dart
│   │       ├── chat_repository.dart
│   │       └── user_repository.dart
│   │
│   ├── models/                        # Data models (freezed)
│   │   ├── user.dart
│   │   ├── dashboard_summary.dart
│   │   ├── insight_data.dart
│   │   ├── chat_message.dart
│   │   ├── conversation.dart
│   │   └── ...
│   │
│   ├── providers/                     # Riverpod providers (global)
│   │   ├── auth_provider.dart
│   │   ├── api_client_provider.dart
│   │   ├── secure_storage_provider.dart
│   │   └── ...
│   │
│   ├── features/                      # Feature-based modules
│   │   │
│   │   ├── auth/
│   │   │   ├── presentation/
│   │   │   │   ├── login_screen.dart
│   │   │   │   └── widgets/
│   │   │   │       ├── biometric_button.dart
│   │   │   │       └── login_logo.dart
│   │   │   ├── application/
│   │   │   │   └── auth_controller.dart
│   │   │   └── domain/
│   │   │       └── auth_state.dart
│   │   │
│   │   ├── dashboard/
│   │   │   ├── presentation/
│   │   │   │   ├── dashboard_screen.dart
│   │   │   │   └── widgets/
│   │   │   │       ├── summary_card.dart
│   │   │   │       ├── stats_row.dart
│   │   │   │       ├── ai_summary_card.dart
│   │   │   │       ├── daily_chart.dart
│   │   │   │       └── highlight_list.dart
│   │   │   ├── application/
│   │   │   │   └── dashboard_controller.dart
│   │   │   └── domain/
│   │   │       └── dashboard_state.dart
│   │   │
│   │   ├── chat/
│   │   │   ├── presentation/
│   │   │   │   ├── chat_screen.dart
│   │   │   │   └── widgets/
│   │   │   │       ├── message_bubble.dart
│   │   │   │       ├── rich_card.dart
│   │   │   │       ├── suggestion_chips.dart
│   │   │   │       └── chat_input.dart
│   │   │   ├── application/
│   │   │   │   ├── chat_controller.dart
│   │   │   │   └── message_stream.dart
│   │   │   └── domain/
│   │   │       └── chat_state.dart
│   │   │
│   │   ├── insight/
│   │   │   ├── presentation/
│   │   │   │   ├── insight_screen.dart
│   │   │   │   └── widgets/
│   │   │   │       ├── kpi_grid.dart
│   │   │   │       ├── composition_donut.dart
│   │   │   │       └── analysis_card.dart
│   │   │   ├── application/
│   │   │   │   └── insight_controller.dart
│   │   │   └── domain/
│   │   │       └── insight_state.dart
│   │   │
│   │   └── shell/                      # Bottom nav shell
│   │       └── presentation/
│   │           ├── shell_scaffold.dart
│   │           └── widgets/
│   │               └── bottom_nav.dart
│   │
│   ├── widgets/                       # Reusable widgets (cross-feature)
│   │   ├── emas_card.dart
│   │   ├── emas_button.dart
│   │   ├── emas_input.dart
│   │   ├── emas_avatar.dart
│   │   ├── emas_alert.dart
│   │   ├── emas_loading.dart          # Shimmer loading
│   │   ├── emas_error_view.dart
│   │   ├── emas_empty_view.dart
│   │   └── charts/
│   │       ├── emas_sparkline.dart
│   │       ├── emas_donut.dart
│   │       └── emas_bar_chart.dart
│   │
│   ├── utils/                         # Utilities
│   │   ├── formatters/
│   │   │   ├── currency_formatter.dart
│   │   │   ├── date_formatter.dart
│   │   │   └── number_formatter.dart
│   │   ├── extensions/
│   │   │   ├── context_extension.dart
│   │   │   ├── string_extension.dart
│   │   │   └── datetime_extension.dart
│   │   ├── logger.dart
│   │   └── biometric_helper.dart
│   │
│   └── l10n/                          # Localization
│       ├── app_en.arb                 # (Phase 2)
│       └── app_id.arb
│
├── test/                              # Tests
│   ├── unit/
│   │   ├── api/
│   │   ├── models/
│   │   └── utils/
│   ├── widget/
│   │   ├── widgets/
│   │   └── features/
│   ├── integration/
│   │   └── app_flow_test.dart
│   └── mocks/
│       └── mock_data.dart
│
├── analysis_options.yaml              # Lint rules
├── pubspec.yaml                       # Dependencies
├── pubspec.lock                       # Lock file (committed)
├── .gitignore
├── README.md                          # App-specific readme
└── CHANGELOG.md                       # Version history
```

---

## Architecture Pattern

App ini pakai **Feature-First + Clean Architecture (3-layer)**:

```
┌─────────────────────────────────────────┐
│         Presentation Layer              │
│  (Widget, Screen, Controller-side UI)   │
└─────────────────────────────────────────┘
              ↓ (read state) ↑ (call action)
┌─────────────────────────────────────────┐
│         Application Layer               │
│  (Controller, StateNotifier, Provider)  │
└─────────────────────────────────────────┘
              ↓ (call method)   ↑ (return data)
┌─────────────────────────────────────────┐
│           Domain Layer                  │
│  (Repository interface, Entity, State)  │
└─────────────────────────────────────────┘
              ↓ (impl)          ↑ (impl)
┌─────────────────────────────────────────┐
│       Infrastructure Layer              │
│  (API client, Storage, Repository impl) │
└─────────────────────────────────────────┘
```

### Per-feature folder convention

```
features/<feature_name>/
├── presentation/      # UI - widget, screen
├── application/       # Controller, StateNotifier
└── domain/            # State definition, business logic
```

---

## State Management — Riverpod 2

### Provider Types Used

| Provider | Usage |
|---|---|
| `Provider` | Dependency injection (repositories, services) |
| `StateProvider` | Simple state (filter, period) |
| `NotifierProvider` | Controller with methods (Riverpod 2.x style) |
| `AsyncNotifierProvider` | Controller with async load |
| `StreamProvider` | Real-time data (chat streaming) |
| `FutureProvider` | One-shot async (initial load) |

### Example: Dashboard Controller

```dart
// lib/features/dashboard/application/dashboard_controller.dart
@riverpod
class DashboardController extends _$DashboardController {
  @override
  Future<DashboardState> build() async {
    return _loadInitial();
  }
  
  Future<DashboardState> _loadInitial() async {
    final repo = ref.read(dashboardRepositoryProvider);
    final period = ref.read(selectedPeriodProvider);
    final summary = await repo.getSummary(period: period);
    return DashboardState.success(summary);
  }
  
  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(_loadInitial);
  }
  
  Future<void> changePeriod(Period period) async {
    ref.read(selectedPeriodProvider.notifier).state = period;
    await refresh();
  }
}
```

### Best Practices

- **Setiap screen** punya controller terpisah di `application/`
- **Domain state** define di `domain/<feature>_state.dart` pakai `freezed`
- **Side effects** (API call, navigation) di controller, **bukan di widget**
- **Widget** cuma read state + dispatch action
- **Hindari** `setState()` — selalu via Riverpod

---

## Routing — go_router

### Route Structure

```dart
// lib/routing/app_router.dart
final appRouter = GoRouter(
  initialLocation: '/',
  redirect: (context, state) {
    final auth = ref.read(authStateProvider);
    if (!auth.isAuthenticated && state.path != '/login') {
      return '/login';
    }
    return null;
  },
  routes: [
    GoRoute(
      path: '/login',
      builder: (ctx, state) => const LoginScreen(),
    ),
    ShellRoute(
      builder: (ctx, state, child) => ShellScaffold(child: child),
      routes: [
        GoRoute(
          path: '/',
          name: 'dashboard',
          builder: (ctx, state) => const DashboardScreen(),
        ),
        GoRoute(
          path: '/insight',
          name: 'insight',
          builder: (ctx, state) => const InsightScreen(),
        ),
        GoRoute(
          path: '/chat',
          name: 'chat',
          builder: (ctx, state) => const ChatScreen(),
        ),
        GoRoute(
          path: '/reports',
          name: 'reports',
          builder: (ctx, state) => const ReportsScreen(),
        ),
        GoRoute(
          path: '/profile',
          name: 'profile',
          builder: (ctx, state) => const ProfileScreen(),
        ),
      ],
    ),
  ],
);
```

### Navigation

✅ **Benar**:
```dart
context.go('/insight');
context.goNamed('insight');
context.push('/chat?context=insight');
```

❌ **Salah**:
```dart
Navigator.push(...) // pakai go_router consistently
```

---

## Dependencies — pubspec.yaml

```yaml
name: emas_berlian_insight
description: Executive Business Intelligence for Lumbung Emas
version: 1.0.0+1
publish_to: none

environment:
  sdk: '>=3.5.0 <4.0.0'
  flutter: '>=3.24.0'

dependencies:
  flutter:
    sdk: flutter
  flutter_localizations:
    sdk: flutter
  
  # State Management
  flutter_riverpod: ^2.5.1
  riverpod_annotation: ^2.3.5
  
  # Routing
  go_router: ^14.2.0
  
  # Network
  dio: ^5.5.0
  dio_cache_interceptor: ^3.5.0
  pretty_dio_logger: ^1.4.0
  
  # Storage
  flutter_secure_storage: ^9.2.2
  shared_preferences: ^2.3.0
  hive_flutter: ^1.1.0
  
  # Models
  freezed_annotation: ^2.4.4
  json_annotation: ^4.9.0
  
  # UI
  google_fonts: ^6.2.1
  flutter_svg: ^2.0.10
  fl_chart: ^0.68.0
  shimmer: ^3.0.0
  cached_network_image: ^3.4.0
  
  # Utils
  intl: ^0.19.0
  collection: ^1.18.0
  fpdart: ^1.1.0
  
  # Biometric
  local_auth: ^2.3.0
  local_auth_android: ^1.0.43
  local_auth_darwin: ^1.4.0
  
  # Logging
  logger: ^2.4.0
  
  # Device info
  device_info_plus: ^10.1.0
  package_info_plus: ^8.0.0
  
  # Connectivity
  connectivity_plus: ^6.0.0
  
  # Crash reporting (Phase 1.5)
  # sentry_flutter: ^8.6.0

dev_dependencies:
  flutter_test:
    sdk: flutter
  integration_test:
    sdk: flutter
  
  # Codegen
  build_runner: ^2.4.11
  freezed: ^2.5.2
  json_serializable: ^6.8.0
  riverpod_generator: ^2.4.0
  
  # Lint
  flutter_lints: ^4.0.0
  custom_lint: ^0.6.4
  riverpod_lint: ^2.3.10
  
  # Test
  mocktail: ^1.0.4
  golden_toolkit: ^0.15.0
  
  # CI
  flutter_launcher_icons: ^0.13.1
  flutter_native_splash: ^2.4.1

flutter:
  uses-material-design: true
  
  assets:
    - assets/svg/
    - assets/images/
  
  # Fonts via google_fonts package
```

---

## Lint Configuration — analysis_options.yaml

```yaml
include: package:flutter_lints/flutter.yaml

analyzer:
  exclude:
    - "**/*.g.dart"
    - "**/*.freezed.dart"
    - "lib/generated_plugin_registrant.dart"
  
  errors:
    invalid_annotation_target: ignore
  
  language:
    strict-casts: true
    strict-inference: true
    strict-raw-types: true

linter:
  rules:
    # Custom rules
    avoid_print: error
    prefer_const_constructors: true
    prefer_const_literals_to_create_immutables: true
    prefer_single_quotes: true
    require_trailing_commas: true
    sort_constructors_first: true
    
    # Riverpod
    unawaited_futures: error
    
    # Documentation
    public_member_api_docs: false  # opsional, set true kalau strict
```

---

## Environment Configuration

### Multi-flavor

App ini punya 3 flavor: `dev`, `staging`, `prod`.

```bash
# Run dev
flutter run --flavor dev --dart-define=ENV=dev

# Run staging
flutter run --flavor staging --dart-define=ENV=staging

# Build prod
flutter build apk --release --flavor prod --dart-define=ENV=prod
```

### env.dart

```dart
class Env {
  static const String env = String.fromEnvironment('ENV', defaultValue: 'dev');
  
  static String get apiBaseUrl {
    switch (env) {
      case 'prod':
        return 'https://codi.lumbungemas.internal/api/v1';
      case 'staging':
        return 'https://staging.codi.lumbungemas.internal/api/v1';
      default:
        return 'http://localhost:8787/api/v1';
    }
  }
  
  static bool get isProduction => env == 'prod';
  static bool get enableLogging => !isProduction;
}
```

---

## Build & Distribution

### iOS

```bash
# Build for TestFlight
flutter build ipa --release --flavor prod --dart-define=ENV=prod

# Upload via Xcode atau fastlane
```

### Android

```bash
# Build APK untuk Firebase App Distribution
flutter build apk --release --flavor prod --dart-define=ENV=prod

# Atau AAB untuk Play Store (kalau perlu)
flutter build appbundle --release --flavor prod --dart-define=ENV=prod
```

### Distribution Plan

- **iOS**: TestFlight, max 100 internal tester. Invite Bapak Leo via email.
- **Android**: Firebase App Distribution. Send install link via WhatsApp.

---

## Code Generation

Setiap kali ubah `freezed`, `json_serializable`, atau `riverpod_annotation`:

```bash
dart run build_runner build --delete-conflicting-outputs

# Atau watch mode saat development
dart run build_runner watch --delete-conflicting-outputs
```

---

## Performance Guidelines

- **Const constructor everywhere** — bantu rebuild optimization
- **Lazy loading** — gunakan `ListView.builder`, jangan render semua sekaligus
- **Image caching** — pakai `cached_network_image`
- **Riverpod scoping** — gunakan `select` untuk avoid unnecessary rebuild
- **Heavy computation** — `compute()` untuk parsing JSON besar
- **Avoid setState in build** — selalu via Riverpod
