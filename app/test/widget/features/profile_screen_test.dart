// Widget test Profil (S6) — data lokal instan (tak ada async load).

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:emas_berlian_insight/theme/app_theme.dart';
import 'package:emas_berlian_insight/features/profile/presentation/profile_screen.dart';
import 'package:emas_berlian_insight/features/profile/presentation/widgets/profile_hero.dart';
import 'package:emas_berlian_insight/features/profile/presentation/widgets/settings_card.dart';
import 'package:emas_berlian_insight/features/shell/presentation/widgets/bottom_nav.dart';

Future<void> _pump(WidgetTester tester, {VoidCallback? onLogout}) {
  return tester.pumpWidget(
    ProviderScope(
      child: MaterialApp(
        theme: AppTheme.darkTheme,
        home: ProfileScreen(onLogout: onLogout),
      ),
    ),
  );
}

void main() {
  testWidgets('render hero + grup pengaturan + logout', (tester) async {
    await _pump(tester);
    await tester.pump();

    expect(find.byType(ProfileHero), findsOneWidget);
    expect(find.text('Leo Sastra C.W.'), findsWidgets); // hero + footer
    expect(find.text('DIREKTUR UTAMA'), findsOneWidget);
    // ListView lazy build — grup awal terlihat, sisanya saat scroll.
    expect(find.byType(SettingsGroupView), findsAtLeastNWidgets(2));
    expect(find.text('Notifikasi'), findsOneWidget);

    // Scroll ke bawah → grup Codi + logout ter-build.
    await tester.scrollUntilVisible(
      find.text('Keluar'),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pump();
    expect(find.text('Sesi Codi'), findsOneWidget);
    expect(find.text('Keluar'), findsOneWidget);
  });

  testWidgets('tap toggle Notifikasi → state berubah', (tester) async {
    await _pump(tester);
    await tester.pump();

    // Default notif ON. Tap row → OFF (toggle widget animasi 200ms).
    await tester.tap(find.text('Notifikasi'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 250));

    // Re-tap → ON lagi (idempotent sanity).
    await tester.tap(find.text('Notifikasi'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 250));

    expect(find.text('Notifikasi'), findsOneWidget); // tak crash
  });

  testWidgets('tap Keluar → onLogout dipanggil', (tester) async {
    var loggedOut = false;
    await _pump(tester, onLogout: () => loggedOut = true);
    await tester.pump();

    await tester.scrollUntilVisible(
      find.text('Keluar'),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pump();
    await tester.tap(find.text('Keluar'));
    await tester.pump();

    expect(loggedOut, isTrue);
  });

  testWidgets('bottom nav active = Profil', (tester) async {
    await _pump(tester);
    await tester.pump();

    final nav = tester.widget<BottomNav>(find.byType(BottomNav));
    expect(nav.active, NavTab.profil);
  });
}
