import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/profile_data.dart';

/// Controller Profil (S6).
///
/// **Mock data** sesuai mockup `docs/emas-berlian-insight.html`
/// (SCREEN 6). Identitas statik (single-user app), toggle preferensi
/// in-memory (belum persist — tunggu backend / local storage,
/// `docs/04-API-CONTRACT.md`). Tak ada async load: data lokal, instan.
class ProfileController extends Notifier<ProfileData> {
  @override
  ProfileData build() => _seed();

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

  ProfileData _seed() {
    return const ProfileData(
      name: 'Leo Sastra C.W.',
      initials: 'LS',
      role: 'Direktur Utama',
      org: 'PT Emas Berlian · Kantor Operasional',
      footer: 'Emas Berlian Insight · Powered by Codi',
      groups: [
        SettingsGroup(
          label: 'Akun',
          items: [
            SettingsItem(
              id: 'identitas',
              title: 'Identitas',
              subtitle: 'leo.sastra · Akses Direksi',
              trailing: SettingsTrailing.chevron,
            ),
            SettingsItem(
              id: 'perusahaan',
              title: 'Perusahaan',
              subtitle: 'PT Emas Berlian',
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
        SettingsGroup(
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
}

/// Provider state Profil.
final profileControllerProvider =
    NotifierProvider<ProfileController, ProfileData>(
  ProfileController.new,
);
