import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/profile_data.dart';
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
    return _seed(store);
  }

  /// Toggle item preferensi (notifikasi, refresh otomatis).
  void toggle(String id) {
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
                  it.copyWith(toggleOn: !it.toggleOn)
                else
                  it,
            ],
          ),
      ],
    );
  }

  ProfileData _seed(TokenStore store) {
    final name = store.name.isNotEmpty ? store.name : 'Direksi';
    final title = store.title.isNotEmpty ? store.title : '';
    final email = store.email.isNotEmpty ? store.email : '-';
    final initials = _initialsFromName(name);
    return ProfileData(
      name: name,
      initials: initials,
      role: title,
      org: 'PT Emas Berlian · Kantor Operasional',
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
              subtitle: 'PT Emas Berlian',
              trailing: SettingsTrailing.chevron,
            ),
          ],
        ),
        const SettingsGroup(
          label: 'Preferensi',
          items: [
            SettingsItem(
              id: 'tema',
              title: 'Tema',
              subtitle: 'Ikuti sistem',
              trailing: SettingsTrailing.value,
              value: 'Sistem',
            ),
            SettingsItem(
              id: 'notifikasi',
              title: 'Notifikasi',
              subtitle: 'Ringkasan harian & alert',
              trailing: SettingsTrailing.toggle,
              toggleOn: true,
            ),
            SettingsItem(
              id: 'refresh',
              title: 'Refresh otomatis',
              subtitle: 'Perbarui data tiap buka app',
              trailing: SettingsTrailing.toggle,
              toggleOn: true,
            ),
          ],
        ),
        const SettingsGroup(
          label: 'Codi',
          items: [
            SettingsItem(
              id: 'sesi',
              title: 'Sesi Codi',
              subtitle: '2 sesi aktif · idle 12 mnt',
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
        'superadmin' => 'Super Admin',
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
