import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/profile_data.dart';
import '../../../providers/settings_store.dart';
import '../../../providers/token_store.dart';

/// Controller Profil (S6).
///
/// **Mock data** sesuai mockup `docs/emas-berlian-insight.html`
/// (SCREEN 6). Identitas statik (single-user app), toggle preferensi
/// in-memory (belum persist — tunggu backend / local storage,
/// `docs/04-API-CONTRACT.md`). Tak ada async load: data lokal, instan.
class ProfileController extends Notifier<ProfileData> {
  @override
  ProfileData build() {
    final store = ref.read(tokenStoreProvider);
    // Tema reaktif: rebuild ProfileData saat mode tema berubah agar value
    // baris "Tema" ikut update.
    final themeMode = ref.watch(themeModeProvider);
    final settings = ref.read(settingsStoreProvider);
    return _seed(store, themeMode, settings);
  }

  /// Toggle item preferensi (notifikasi, refresh otomatis) — persist lokal.
  void toggle(String id) {
    final settings = ref.read(settingsStoreProvider);
    state = ProfileData(
      name: state.name,
      initials: state.initials,
      role: state.role,
      org: state.org,
      footer: state.footer,
      groups: [
        for (final g in state.groups)
          SettingsGroup(
            label: g.label,
            items: [
              for (final it in g.items)
                if (it.id == id && it.trailing == SettingsTrailing.toggle)
                  _persistToggle(settings, it)
                else
                  it,
            ],
          ),
      ],
    );
  }

  SettingsItem _persistToggle(SettingsStore settings, SettingsItem it) {
    final next = !it.toggleOn;
    switch (it.id) {
      case 'notifikasi':
        settings.setNotifikasi(next);
      case 'refresh':
        settings.setRefreshOtomatis(next);
    }
    return it.copyWith(toggleOn: next);
  }

  static String themeLabel(ThemeMode mode) => switch (mode) {
        ThemeMode.light => 'Terang',
        ThemeMode.dark => 'Gelap',
        ThemeMode.system => 'Sistem',
      };

  ProfileData _seed(
    TokenStore store,
    ThemeMode themeMode,
    SettingsStore settings,
  ) {
    final name = store.name.isNotEmpty ? store.name : 'Direksi';
    final email = store.email.isNotEmpty ? store.email : '-';
    final initials = _initialsFromName(name);
    // Superadmin → "IT Supervisor" override (cosmetic). Role lain pakai
    // title personal dari DB, fallback ke role label.
    final role = store.role == 'superadmin'
        ? 'IT Supervisor'
        : (store.title.isNotEmpty ? store.title : _roleLabel(store.role));
    return ProfileData(
      name: name,
      initials: initials,
      role: role,
      org: 'PT Odc Inter Rotasi · Kantor Operasional',
      footer: 'Emas Berlian Insight · Powered by Codi',
      groups: [
        SettingsGroup(
          label: 'Akun',
          items: [
            SettingsItem(
              id: 'identitas',
              title: 'Identitas',
              subtitle: '$email · ${_roleLabel(store.role)}',
              trailing: SettingsTrailing.chevron,
            ),
            const SettingsItem(
              id: 'perusahaan',
              title: 'Perusahaan',
              subtitle: 'PT Odc Inter Rotasi',
              trailing: SettingsTrailing.chevron,
            ),
          ],
        ),
        SettingsGroup(
          label: 'Preferensi',
          items: [
            SettingsItem(
              id: 'tema',
              title: 'Tema',
              subtitle: 'Tampilan aplikasi',
              trailing: SettingsTrailing.value,
              value: themeLabel(themeMode),
            ),
            SettingsItem(
              id: 'notifikasi',
              title: 'Notifikasi',
              subtitle: 'Ringkasan harian & alert',
              trailing: SettingsTrailing.toggle,
              toggleOn: settings.notifikasi,
            ),
            SettingsItem(
              id: 'refresh',
              title: 'Refresh otomatis',
              subtitle: 'Perbarui data tiap buka app',
              trailing: SettingsTrailing.toggle,
              toggleOn: settings.refreshOtomatis,
            ),
          ],
        ),
        const SettingsGroup(
          label: 'Codi',
          items: [
            SettingsItem(
              id: 'sesi',
              title: 'Sesi Codi',
              subtitle: 'Sesi orchestrator aktif',
              trailing: SettingsTrailing.chevron,
            ),
            SettingsItem(
              id: 'tentang',
              title: 'Tentang',
              subtitle: 'Versi & lisensi',
              trailing: SettingsTrailing.value,
              value: 'v1.0.0',
            ),
          ],
        ),
      ],
    );
  }

  static String _initialsFromName(String name) {
    final parts = name.trim().split(RegExp(r'\s+'));
    if (parts.isEmpty || parts.first.isEmpty) return '?';
    if (parts.length == 1) return parts.first.substring(0, 1).toUpperCase();
    return (parts.first[0] + parts.last[0]).toUpperCase();
  }

  static String _roleLabel(String slug) => switch (slug) {
        'superadmin' => 'IT Supervisor',
        'admin' => 'Admin',
        'director' => 'Direksi',
        'viewer' => 'Viewer',
        '' => 'Akses Direksi',
        _ => slug,
      };
}

/// Provider state Profil.
final profileControllerProvider =
    NotifierProvider<ProfileController, ProfileData>(
  ProfileController.new,
);
