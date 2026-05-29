// Widget test EditProfileSheet (S7) — validasi + save.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'package:emas_berlian_insight/theme/app_theme.dart';
import 'package:emas_berlian_insight/features/management/domain/account.dart';
import 'package:emas_berlian_insight/features/management/presentation/widgets/edit_profile_sheet.dart';

ManagedAccount _acc() => const ManagedAccount(
      id: 'acc_1',
      email: 'budi@emasberlian.com',
      name: 'Budi Santoso',
      title: 'Manajer',
      role: 'admin',
      status: 'active',
    );

const _roles = [
  ManagedRole(slug: 'admin', name: 'Admin', scopes: ['accounts:read']),
  ManagedRole(slug: 'director', name: 'Direksi', scopes: ['dashboard:read']),
];

Future<void> _pump(
  WidgetTester tester, {
  required Future<String?> Function({String? name, String? title, String? email})
      onUpdateProfile,
  Future<String?> Function(String role)? onUpdateRole,
}) {
  tester.view.physicalSize = const Size(900, 1600);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  return tester.pumpWidget(
    MaterialApp(
      theme: AppTheme.darkTheme,
      home: Scaffold(
        body: EditProfileSheet(
          account: _acc(),
          roles: _roles,
          canMutateRole: true,
          onUpdateProfile: onUpdateProfile,
          onUpdateRole: onUpdateRole ?? (_) async => null,
        ),
      ),
    ),
  );
}

void main() {
  setUpAll(() async {
    await initializeDateFormatting('id_ID');
  });

  testWidgets('render form + section + scope preview', (tester) async {
    await _pump(tester, onUpdateProfile: ({name, title, email}) async => null);
    await tester.pump();

    expect(find.text('Edit Profil'), findsOneWidget);
    expect(find.text('IDENTITAS'), findsOneWidget);
    expect(find.text('AKSES'), findsOneWidget);
    expect(find.text('INFO AKUN'), findsOneWidget);
    expect(find.text('accounts:read'), findsOneWidget); // scope chip
  });

  testWidgets('nama kosong → error, onUpdateProfile tak dipanggil',
      (tester) async {
    var called = false;
    await _pump(tester, onUpdateProfile: ({name, title, email}) async {
      called = true;
      return null;
    });
    await tester.pump();

    await tester.enterText(find.byType(TextField).first, '');
    await tester.tap(find.text('Simpan'));
    await tester.pump();

    expect(find.text('Nama wajib diisi.'), findsOneWidget);
    expect(called, isFalse);
  });

  testWidgets('email invalid → error', (tester) async {
    await _pump(tester, onUpdateProfile: ({name, title, email}) async => null);
    await tester.pump();

    // Field ke-3 = email.
    await tester.enterText(find.byType(TextField).at(2), 'bukan-email');
    await tester.tap(find.text('Simpan'));
    await tester.pump();

    expect(find.text('Format email tidak valid.'), findsOneWidget);
  });

  testWidgets('edit valid → onUpdateProfile dipanggil dgn nama baru',
      (tester) async {
    String? sentName;
    await _pump(tester, onUpdateProfile: ({name, title, email}) async {
      sentName = name;
      return null;
    });
    await tester.pump();

    await tester.enterText(find.byType(TextField).first, 'Budi Hartono');
    await tester.tap(find.text('Simpan'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    expect(sentName, 'Budi Hartono');
  });
}
