# 08 — TESTING.md

Strategi testing dan quality gate untuk Emas Berlian Insight.

---

## Filosofi Testing

App ini menampilkan data finansial sensitif kepada decision-maker. **Bug = decision salah = uang hilang.**

Karena itu:
- **Test sebanyak yang bisa**, tapi **prioritize critical paths**
- **Lebih baik test minim tapi reliable** daripada banyak tapi flaky
- **Test pyramid** — banyak unit, beberapa widget, sedikit integration

### Pyramid

```
        ┌────────────┐
        │ Integration│   ~10% — end-to-end flow
        │   Tests    │
        └────────────┘
       ┌──────────────┐
       │ Widget Tests │   ~30% — UI behavior
       └──────────────┘
     ┌──────────────────┐
     │   Unit Tests     │   ~60% — business logic
     └──────────────────┘
```

---

## Test Coverage Target

| Layer | Coverage Target | Critical |
|---|---|---|
| Models (freezed) | 80% | Yes |
| Repositories | 90% | Yes |
| Controllers (Riverpod) | 85% | Yes |
| Utils (formatters, helpers) | 95% | Yes |
| Widgets (reusable) | 70% | Medium |
| Screens | 60% | Medium |
| Integration | 100% critical flows | Yes |

**Critical flows yang HARUS ada integration test**:
1. Login → Dashboard
2. Dashboard → Insight → Back
3. Dashboard → Chat → Send Message → Receive Response
4. Token expired → auto refresh → continue
5. Offline → load cache → reconnect → refresh

---

## Tools & Setup

### Dependencies (sudah di pubspec)

```yaml
dev_dependencies:
  flutter_test:
    sdk: flutter
  integration_test:
    sdk: flutter
  mocktail: ^1.0.4              # Mocking
  golden_toolkit: ^0.15.0       # Visual regression
  riverpod_lint: ^2.3.10        # Lint Riverpod patterns
```

### Folder Structure

```
test/
├── unit/
│   ├── api/
│   │   ├── api_client_test.dart
│   │   └── repositories/
│   │       ├── auth_repository_test.dart
│   │       ├── dashboard_repository_test.dart
│   │       └── chat_repository_test.dart
│   ├── models/
│   │   ├── user_test.dart
│   │   ├── dashboard_summary_test.dart
│   │   └── ...
│   ├── controllers/
│   │   ├── auth_controller_test.dart
│   │   ├── dashboard_controller_test.dart
│   │   └── ...
│   └── utils/
│       ├── currency_formatter_test.dart
│       ├── date_formatter_test.dart
│       └── ...
├── widget/
│   ├── widgets/
│   │   ├── emas_card_test.dart
│   │   ├── emas_button_test.dart
│   │   └── ...
│   └── features/
│       ├── auth/
│       │   └── login_screen_test.dart
│       ├── dashboard/
│       │   └── dashboard_screen_test.dart
│       └── ...
├── integration/
│   ├── app_flow_test.dart
│   ├── login_flow_test.dart
│   ├── chat_flow_test.dart
│   └── offline_flow_test.dart
├── golden/
│   └── widgets/                # Visual regression baseline
└── mocks/
    ├── mock_data.dart           # Sample data
    ├── mock_repositories.dart
    └── test_helpers.dart
```

---

## Unit Tests

### Model Tests

Test JSON serialization & business logic:

```dart
// test/unit/models/dashboard_summary_test.dart
void main() {
  group('DashboardSummary', () {
    test('parses JSON correctly', () {
      final json = {
        'period': 'month',
        'revenue': {'total': 828882000, 'currency': 'IDR'},
        // ...
      };
      
      final summary = DashboardSummary.fromJson(json);
      
      expect(summary.period, 'month');
      expect(summary.revenue.total, 828882000);
    });
    
    test('handles missing optional fields', () {
      final json = {'period': 'month', 'revenue': {'total': 0}};
      final summary = DashboardSummary.fromJson(json);
      expect(summary.aiSummary, isNull);
    });
    
    test('formattedRevenue returns Indonesian format', () {
      final revenue = Revenue(total: 828882000);
      expect(revenue.formatted, 'Rp 828.882.000');
    });
  });
}
```

### Repository Tests

Mock Dio, test repository behavior:

```dart
// test/unit/api/repositories/dashboard_repository_test.dart
class MockDio extends Mock implements Dio {}

void main() {
  late MockDio mockDio;
  late DashboardRepository repo;
  
  setUp(() {
    mockDio = MockDio();
    repo = DashboardRepository(mockDio);
  });
  
  test('getSummary returns parsed data on success', () async {
    when(() => mockDio.get(any())).thenAnswer(
      (_) async => Response(
        data: mockSummaryJson,
        statusCode: 200,
        requestOptions: RequestOptions(path: ''),
      ),
    );
    
    final result = await repo.getSummary(period: Period.month);
    
    expect(result.revenue.total, 828882000);
  });
  
  test('getSummary throws ApiException on 500', () async {
    when(() => mockDio.get(any())).thenThrow(
      DioException(
        response: Response(statusCode: 500, requestOptions: RequestOptions(path: '')),
        requestOptions: RequestOptions(path: ''),
      ),
    );
    
    expect(
      () => repo.getSummary(period: Period.month),
      throwsA(isA<ApiException>()),
    );
  });
}
```

### Controller Tests

Test Riverpod controller transitions:

```dart
// test/unit/controllers/dashboard_controller_test.dart
class MockDashboardRepo extends Mock implements DashboardRepository {}

void main() {
  late MockDashboardRepo mockRepo;
  late ProviderContainer container;
  
  setUp(() {
    mockRepo = MockDashboardRepo();
    container = ProviderContainer(
      overrides: [
        dashboardRepositoryProvider.overrideWithValue(mockRepo),
      ],
    );
  });
  
  tearDown(() => container.dispose());
  
  test('loads data on init', () async {
    when(() => mockRepo.getSummary(period: any(named: 'period')))
        .thenAnswer((_) async => mockSummary);
    
    final state = await container.read(dashboardControllerProvider.future);
    
    expect(state, isA<DashboardSuccess>());
    expect((state as DashboardSuccess).data.revenue.total, 828882000);
  });
  
  test('handles error state', () async {
    when(() => mockRepo.getSummary(period: any(named: 'period')))
        .thenThrow(ApiException('Server error'));
    
    final state = container.read(dashboardControllerProvider);
    
    await expectLater(
      container.read(dashboardControllerProvider.future),
      throwsA(isA<ApiException>()),
    );
  });
}
```

### Utility Tests

Critical for business logic:

```dart
// test/unit/utils/currency_formatter_test.dart
void main() {
  group('CurrencyFormatter', () {
    test('formats IDR correctly', () {
      expect(CurrencyFormatter.format(828882000), 'Rp 828.882.000');
      expect(CurrencyFormatter.format(1500), 'Rp 1.500');
      expect(CurrencyFormatter.format(0), 'Rp 0');
    });
    
    test('compact format for large numbers', () {
      expect(CurrencyFormatter.compact(828882000), 'Rp 828,8 jt');
      expect(CurrencyFormatter.compact(1500000000), 'Rp 1,5 M');
      expect(CurrencyFormatter.compact(500000), 'Rp 500 rb');
      expect(CurrencyFormatter.compact(0), 'Rp 0');
    });
    
    test('handles edge cases', () {
      expect(CurrencyFormatter.format(-1000), '-Rp 1.000');
      expect(CurrencyFormatter.format(null), '—');
    });
  });
}
```

---

## Widget Tests

### Custom Widget Test

```dart
// test/widget/widgets/emas_button_test.dart
void main() {
  group('EmasButton', () {
    testWidgets('renders primary variant correctly', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.darkTheme,
          home: Scaffold(
            body: EmasButton.primary(
              onPressed: () {},
              label: 'Test Button',
            ),
          ),
        ),
      );
      
      expect(find.text('Test Button'), findsOneWidget);
      
      final container = tester.widget<Container>(
        find.descendant(
          of: find.byType(EmasButton),
          matching: find.byType(Container),
        ),
      );
      
      expect(
        (container.decoration as BoxDecoration).gradient,
        isNotNull,
      );
    });
    
    testWidgets('calls onPressed when tapped', (tester) async {
      var pressed = false;
      
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: EmasButton.primary(
              onPressed: () => pressed = true,
              label: 'Tap me',
            ),
          ),
        ),
      );
      
      await tester.tap(find.byType(EmasButton));
      
      expect(pressed, isTrue);
    });
    
    testWidgets('disabled state prevents tap', (tester) async {
      var pressed = false;
      
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: EmasButton.primary(
              onPressed: null,  // disabled
              label: 'Disabled',
            ),
          ),
        ),
      );
      
      await tester.tap(find.byType(EmasButton));
      
      expect(pressed, isFalse);
    });
  });
}
```

### Screen Test

```dart
// test/widget/features/dashboard/dashboard_screen_test.dart
void main() {
  testWidgets('shows loading state initially', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          dashboardControllerProvider.overrideWith(
            () => AlwaysLoadingDashboardController(),
          ),
        ],
        child: MaterialApp(home: DashboardScreen()),
      ),
    );
    
    expect(find.byType(Shimmer), findsWidgets);
  });
  
  testWidgets('shows data after load', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          dashboardControllerProvider.overrideWith(
            () => MockDashboardController(initialData: mockSummary),
          ),
        ],
        child: MaterialApp(home: DashboardScreen()),
      ),
    );
    
    await tester.pumpAndSettle();
    
    expect(find.text('Rp 828,8jt'), findsOneWidget);
    expect(find.text('+321% MoM'), findsOneWidget);
  });
  
  testWidgets('pull to refresh triggers reload', (tester) async {
    final controller = MockDashboardController(initialData: mockSummary);
    
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          dashboardControllerProvider.overrideWith(() => controller),
        ],
        child: MaterialApp(home: DashboardScreen()),
      ),
    );
    
    await tester.pumpAndSettle();
    
    await tester.drag(find.byType(CustomScrollView), const Offset(0, 300));
    await tester.pumpAndSettle();
    
    expect(controller.refreshCallCount, greaterThan(0));
  });
}
```

---

## Golden Tests (Visual Regression)

Untuk visual consistency, gunakan `golden_toolkit`:

```dart
// test/widget/widgets/emas_card_golden_test.dart
void main() {
  testGoldens('EmasCard renders correctly', (tester) async {
    await tester.pumpWidgetBuilder(
      EmasCard(child: Text('Test Content')),
      wrapper: materialAppWrapper(theme: AppTheme.darkTheme),
      surfaceSize: Size(300, 100),
    );
    
    await screenMatchesGolden(tester, 'emas_card_default');
  });
  
  testGoldens('Hero summary card matches design', (tester) async {
    await tester.pumpWidgetBuilder(
      SummaryCard(data: mockSummary),
      wrapper: materialAppWrapper(theme: AppTheme.darkTheme),
      surfaceSize: Size(360, 200),
    );
    
    await screenMatchesGolden(tester, 'summary_card_hero');
  });
}
```

### Update Golden

```bash
flutter test --update-goldens
```

Untuk visual review setiap perubahan UI, run golden test di CI dan compare. Kalau ada diff yang intentional, update golden + commit.

---

## Integration Tests

### App Flow Test

```dart
// test/integration/app_flow_test.dart
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  
  group('Full App Flow', () {
    testWidgets('login → dashboard → chat → response', (tester) async {
      // Setup app dengan mock backend
      app.main();
      await tester.pumpAndSettle();
      
      // 1. Login
      await tester.tap(find.byKey(const Key('biometric_button')));
      await tester.pumpAndSettle();
      
      // 2. Dashboard loads
      expect(find.text('OMZET MEI 2026 · LIVE'), findsOneWidget);
      expect(find.text('Rp 828,8jt'), findsOneWidget);
      
      // 3. Open chat via FAB
      await tester.tap(find.byKey(const Key('codi_fab')));
      await tester.pumpAndSettle();
      
      // 4. Send message
      await tester.enterText(
        find.byKey(const Key('chat_input')),
        'Bagaimana kondisi hari ini?',
      );
      await tester.tap(find.byKey(const Key('send_button')));
      await tester.pumpAndSettle();
      
      // 5. Verify response
      expect(find.textContaining('Selamat pagi'), findsOneWidget);
    });
  });
}
```

### Run Integration Test

```bash
# iOS
flutter test integration_test/app_flow_test.dart

# Or on specific device
flutter test integration_test/ -d "iPhone 15 Pro"
```

---

## Mock Data Strategy

### Centralized Mock

```dart
// test/mocks/mock_data.dart
class MockData {
  static DashboardSummary get dashboardSummary => DashboardSummary(
    period: Period.month,
    periodLabel: 'Mei 2026',
    revenue: Revenue(
      total: 828882000,
      currency: 'IDR',
      growthMomPct: 321.0,
    ),
    // ... lengkap
  );
  
  static List<ChatMessage> get chatMessages => [
    ChatMessage(
      id: 'msg_001',
      role: MessageRole.user,
      content: TextContent('Test message'),
      timestamp: DateTime(2026, 5, 17, 9, 42),
    ),
    // ...
  ];
  
  static User get user => User(
    id: 'user_leo_001',
    name: 'Leo Sastra C.W.',
    title: 'Direktur Utama',
    initials: 'LS',
  );
}
```

### JSON Fixtures

Untuk test parsing dari real API response:

```
test/
└── fixtures/
    ├── dashboard_summary.json
    ├── chat_response.json
    └── insight_data.json
```

Load:
```dart
Future<String> loadFixture(String name) async {
  final file = File('test/fixtures/$name');
  return file.readAsString();
}
```

---

## CI Pipeline

### GitHub Actions

```yaml
# .github/workflows/flutter-ci.yml
name: Flutter CI

on:
  push:
    paths:
      - 'apps/emas-berlian-insight/**'
  pull_request:
    paths:
      - 'apps/emas-berlian-insight/**'

jobs:
  test:
    runs-on: macos-latest
    defaults:
      run:
        working-directory: apps/emas-berlian-insight
    
    steps:
      - uses: actions/checkout@v4
      
      - uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.24.x'
          channel: 'stable'
          cache: true
      
      - name: Install dependencies
        run: flutter pub get
      
      - name: Run code generation
        run: dart run build_runner build --delete-conflicting-outputs
      
      - name: Verify formatting
        run: dart format --output=none --set-exit-if-changed .
      
      - name: Analyze
        run: flutter analyze --fatal-infos
      
      - name: Run unit + widget tests
        run: flutter test --coverage
      
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: ./apps/emas-berlian-insight/coverage/lcov.info
```

### Integration Test in CI

Lebih kompleks karena butuh emulator. Bisa pakai Firebase Test Lab atau Codemagic.

---

## Manual Testing Checklist

Sebelum release, manual test di **real device**:

### iOS

- [ ] Cold start <2s di iPhone 12 atau lebih lama
- [ ] Face ID prompt muncul dan berfungsi
- [ ] Dashboard load data <2s setelah login
- [ ] Pull-to-refresh works
- [ ] Chat send + receive <3s
- [ ] Streaming response smooth
- [ ] Rich card render benar
- [ ] Bottom nav animation smooth
- [ ] No layout overflow di semua screen size (iPhone SE → Pro Max)
- [ ] Status bar style (light) consistent
- [ ] Safe area handled (notch & home indicator)
- [ ] Background → foreground state preserved
- [ ] Network offline mode shows cached + banner
- [ ] Network slow (Network Link Conditioner) handled gracefully

### Android

- [ ] Cold start <2.5s di mid-range device
- [ ] Fingerprint prompt muncul
- [ ] Same UX checklist as iOS
- [ ] Back button (gesture & button) handled
- [ ] Status bar tone dark + ink light
- [ ] No crash di Android 8.0+ (min support)

---

## Test Maintenance

### Definition of Done untuk PR

PR tidak di-merge sampai:
- ✅ All existing tests pass
- ✅ New code has tests (matching coverage target)
- ✅ `flutter analyze` zero warning
- ✅ `dart format` applied
- ✅ Manual test di iOS + Android (untuk UI change)
- ✅ Reviewed by Bapak Hans atau senior dev

### Test Smell Detection

Jangan toleransi:
- ❌ Flaky tests (intermittent fail) — fix or remove
- ❌ Tests that test framework (Flutter widget basic behavior)
- ❌ Tests dengan terlalu banyak mocking (sign of bad architecture)
- ❌ Tests yang skip-related: `skip: true` lebih dari 1 minggu

### When Tests Slow

Kalau test suite >2 menit:
- Parallelize dengan `flutter test --concurrency=N`
- Split unit & widget tests
- Mock heavy I/O
- Use `tester.runAsync` sparingly

---

## Final Quality Gates

Sebelum release ke pilot:

1. ✅ `flutter analyze` zero warning
2. ✅ `flutter test` 100% pass
3. ✅ `flutter test integration_test/` 100% pass
4. ✅ Coverage minimum 70% overall
5. ✅ Manual test checklist completed di 2 device real
6. ✅ Performance budget verified via Flutter DevTools
7. ✅ Crash-free rate 100% pada smoke testing
8. ✅ Build size <30MB
9. ✅ No `TODO` comments di critical path
10. ✅ CHANGELOG.md updated
