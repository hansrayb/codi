import 'package:flutter/foundation.dart';

/// Satu baris pengaturan (mockup `.settings-row`). Tipe trailing:
/// chevron (navigasi), value+chevron, atau toggle.
enum SettingsTrailing { chevron, value, toggle }

/// Satu item pengaturan dalam grup.
@immutable
class SettingsItem {
  const SettingsItem({
    required this.id,
    required this.title,
    required this.subtitle,
    required this.trailing,
    this.value,
    this.toggleOn = false,
  });

  /// Identifier stabil (untuk tap handler & test).
  final String id;

  final String title;
  final String subtitle;
  final SettingsTrailing trailing;

  /// Teks value (kalau `trailing == value`), mis. "Sistem", "v1.0.0".
  final String? value;

  /// State toggle (kalau `trailing == toggle`).
  final bool toggleOn;

  SettingsItem copyWith({bool? toggleOn}) => SettingsItem(
        id: id,
        title: title,
        subtitle: subtitle,
        trailing: trailing,
        value: value,
        toggleOn: toggleOn ?? this.toggleOn,
      );
}

/// Grup pengaturan berlabel (mockup `.settings-group`).
@immutable
class SettingsGroup {
  const SettingsGroup({required this.label, required this.items});

  /// Mis. "Akun", "Preferensi", "Codi".
  final String label;
  final List<SettingsItem> items;
}

/// Payload profil — identitas direksi + grup pengaturan
/// (mockup SCREEN 6). Saat ini di-mock.
@immutable
class ProfileData {
  const ProfileData({
    required this.name,
    required this.initials,
    required this.role,
    required this.org,
    required this.groups,
    required this.footer,
  });

  /// Mis. "Leo Sastra C.W.".
  final String name;

  /// Inisial avatar, mis. "LS".
  final String initials;

  /// Mis. "Direktur Utama".
  final String role;

  /// Mis. "PT Emas Berlian · Kantor Operasional".
  final String org;

  final List<SettingsGroup> groups;

  /// Mis. "Emas Berlian Insight · Powered by Codi".
  final String footer;
}
