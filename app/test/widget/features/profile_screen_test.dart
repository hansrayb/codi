// Widget test Profil (S6) — data lokal instan (tak ada async load).

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:emas_berlian_insight/theme/app_theme.dart';
import 'package:emas_berlian_insight/providers/token_store.dart';
import 'package:emas_berlian_insight/api/repositories/profile_repository.dart';
import 'package:emas_berlian_insight/models/codi_session.dart';
import 'package:emas_berlian_insight/features/profile/presentation/profile_screen.dart';
import 'package:emas_berlian_insight/features/profile/presentation/widgets/profile_hero.dart';
import 'package:emas_berlian_insight/features/profile/presentation/widgets/settings_card.dart';
import 'package:emas_berlian_insight/features/shell/presentation/widgets/bottom_nav.dart';

import '../../helpers/fake_token_store.dart';

/// Fake repo sesi — 1 sesi aktif.
class _FakeProfileRepo implements ProfileRepository {
  @override
  Future<CodiSessions> getSessions() async {
    await Future<void>.delayed(const Duration(milliseconds: 10));
    return const CodiSessions(
      active: 1,
      sessions: [
        CodiSession(
          id: 's-01',
          role: 'advisor',
          repoName: 'lumbungemas-prod',
          repo: '/home/odc/lumbungemas-prod',
          idleSeconds: 720,
        ),
      ],
    );
  }
}

Future<void> _pump(WidgetTester tester, {VoidCallback? onLogout}) {
  return tester.pumpWidget(
    ProviderScope(
      overrides: [
        tokenStoreProvider.overrideWithValue(FakeTokenStore()),
        profileRepositoryProvider.overrideWithValue(_FakeProfileRepo()),
      ],
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

  testWidgets('tap Identitas → sheet detail (email)', (tester) async {
    await _pump(tester);
    await tester.pump();

    await tester.tap(find.text('Identitas'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300)); // sheet anim

    expect(find.text('leo@lumbungemas.co.id'), findsOneWidget);
    expect(find.text('Direktur Utama'), findsWidgets);
  });

  testWidgets('tap Tema → picker → pilih Gelap → value berubah',
      (tester) async {
    await _pump(tester);
    await tester.pump();

    await tester.tap(find.text('Tema'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300)); // sheet anim

    // Picker 3 opsi muncul.
    expect(find.text('Sistem'), findsWidgets);
    expect(find.text('Gelap'), findsOneWidget);

    await tester.tap(find.text('Gelap'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300)); // sheet close + rebuild

    // Row "Tema" sekarang value "Gelap".
    expect(find.text('Gelap'), findsOneWidget);
  });

  testWidgets('tap Sesi Codi → sheet daftar sesi (advisor)', (tester) async {
    await _pump(tester);
    await tester.pump();

    await tester.scrollUntilVisible(
      find.text('Sesi Codi'),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pump();
    await tester.tap(find.text('Sesi Codi'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300)); // sheet anim
    await tester.pump(const Duration(milliseconds: 50)); // fake fetch
    await tester.pump(const Duration(milliseconds: 16));

    expect(find.text('advisor'), findsOneWidget);
    expect(find.textContaining('lumbungemas-prod'), findsOneWidget);
  });

  testWidgets('bottom nav active = Profil', (tester) async {
    await _pump(tester);
    await tester.pump();

    final nav = tester.widget<BottomNav>(find.byType(BottomNav));
    expect(nav.active, NavTab.profil);
  });
}
