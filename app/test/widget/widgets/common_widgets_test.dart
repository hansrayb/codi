// Widget test minimum untuk common widgets (Fase 1 Foundation).
//
// Sesuai `docs/01-CLAUDE.md`: setiap widget custom harus punya widget
// test minimum. Cakupan: render tanpa crash + perilaku inti.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:emas_berlian_insight/theme/app_theme.dart';
import 'package:emas_berlian_insight/widgets/widgets.dart';

/// Bungkus widget dengan MaterialApp + theme aplikasi untuk testing.
Future<void> pumpWidget(WidgetTester tester, Widget child) {
  return tester.pumpWidget(
    MaterialApp(
      theme: AppTheme.darkTheme,
      home: Scaffold(body: child),
    ),
  );
}

void main() {
  group('EmasButton', () {
    testWidgets('render label + trigger onPressed', (tester) async {
      var tapped = false;
      await pumpWidget(
        tester,
        EmasButton(label: 'Masuk', onPressed: () => tapped = true),
      );

      expect(find.text('Masuk'), findsOneWidget);
      await tester.tap(find.byType(EmasButton));
      expect(tapped, isTrue);
    });

    testWidgets('disabled saat onPressed null', (tester) async {
      await pumpWidget(
        tester,
        const EmasButton(label: 'Nonaktif', onPressed: null),
      );

      expect(find.text('Nonaktif'), findsOneWidget);
      // Tap tidak crash walau disabled.
      await tester.tap(find.byType(EmasButton));
    });
  });

  group('EmasCard', () {
    testWidgets('render child', (tester) async {
      await pumpWidget(
        tester,
        const EmasCard(child: Text('isi card')),
      );
      expect(find.text('isi card'), findsOneWidget);
    });

    testWidgets('onTap dipanggil', (tester) async {
      var tapped = false;
      await pumpWidget(
        tester,
        EmasCard(onTap: () => tapped = true, child: const Text('tap')),
      );
      await tester.tap(find.text('tap'));
      expect(tapped, isTrue);
    });
  });

  testWidgets('EmasElevatedCard render child', (tester) async {
    await pumpWidget(
      tester,
      const EmasElevatedCard(child: Text('hero')),
    );
    expect(find.text('hero'), findsOneWidget);
  });

  group('EmasAvatar', () {
    testWidgets('inisial 2 kata', (tester) async {
      await pumpWidget(tester, const EmasAvatar(name: 'Leo Sastra'));
      expect(find.text('LS'), findsOneWidget);
    });

    testWidgets('inisial 1 kata ambil 2 char', (tester) async {
      await pumpWidget(tester, const EmasAvatar(name: 'Codi'));
      expect(find.text('CO'), findsOneWidget);
    });

    testWidgets('nama kosong fallback ?', (tester) async {
      await pumpWidget(tester, const EmasAvatar(name: '   '));
      expect(find.text('?'), findsOneWidget);
    });
  });

  testWidgets('EmasInput render hint', (tester) async {
    await pumpWidget(
      tester,
      const EmasInput(hintText: 'Tanya Codi'),
    );
    expect(find.text('Tanya Codi'), findsOneWidget);
  });

  group('EmasAlert', () {
    testWidgets('render title + message', (tester) async {
      await pumpWidget(
        tester,
        const EmasAlert(
          title: 'Sehat',
          message: 'Omzet naik 12%.',
          severity: EmasAlertSeverity.success,
        ),
      );
      expect(find.text('Sehat'), findsOneWidget);
      expect(find.text('Omzet naik 12%.'), findsOneWidget);
    });
  });

  testWidgets('EmasLoadingCard render skeleton', (tester) async {
    await pumpWidget(tester, const EmasLoadingCard());
    expect(find.byType(EmasSkeleton), findsWidgets);
  });

  group('EmasErrorView', () {
    testWidgets('render message + retry', (tester) async {
      var retried = false;
      await pumpWidget(
        tester,
        EmasErrorView(
          message: 'Tidak ada koneksi.',
          onRetry: () => retried = true,
        ),
      );
      expect(find.text('Tidak ada koneksi.'), findsOneWidget);
      await tester.tap(find.text('Coba lagi'));
      expect(retried, isTrue);
    });

    testWidgets('tanpa onRetry, tombol tak muncul', (tester) async {
      await pumpWidget(
        tester,
        const EmasErrorView(message: 'Error.'),
      );
      expect(find.text('Coba lagi'), findsNothing);
    });
  });

  testWidgets('EmasEmptyView render message', (tester) async {
    await pumpWidget(
      tester,
      const EmasEmptyView(message: 'Belum ada data.'),
    );
    expect(find.text('Belum ada data.'), findsOneWidget);
  });
}
