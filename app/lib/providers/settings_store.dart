import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Penyimpanan preferensi lokal (device) via `shared_preferences`.
///
/// Tema, notifikasi, refresh otomatis. Backend `PATCH /me/preferences`
/// saat ini tidak persist (echo-only), jadi preferensi UI disimpan lokal.
/// Cache in-memory agar getter sinkron untuk frame pertama (pola
/// [TokenStore]). Panggil [load] saat bootstrap sebelum `runApp`.
class SettingsStore {
  static const _kTheme = 'pref_theme_mode';
  static const _kNotif = 'pref_notifikasi';
  static const _kRefresh = 'pref_refresh_otomatis';

  SharedPreferences? _prefs;
  ThemeMode _theme = ThemeMode.system;
  bool _notifikasi = true;
  bool _refreshOtomatis = true;

  ThemeMode get themeMode => _theme;
  bool get notifikasi => _notifikasi;
  bool get refreshOtomatis => _refreshOtomatis;

  /// Muat preferensi tersimpan ke cache.
  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    _prefs = prefs;
    _theme = _parseTheme(prefs.getString(_kTheme));
    _notifikasi = prefs.getBool(_kNotif) ?? true;
    _refreshOtomatis = prefs.getBool(_kRefresh) ?? true;
  }

  Future<void> setThemeMode(ThemeMode mode) async {
    _theme = mode;
    await _prefs?.setString(_kTheme, mode.name);
  }

  Future<void> setNotifikasi(bool value) async {
    _notifikasi = value;
    await _prefs?.setBool(_kNotif, value);
  }

  Future<void> setRefreshOtomatis(bool value) async {
    _refreshOtomatis = value;
    await _prefs?.setBool(_kRefresh, value);
  }

  static ThemeMode _parseTheme(String? v) => switch (v) {
        'light' => ThemeMode.light,
        'dark' => ThemeMode.dark,
        _ => ThemeMode.system,
      };
}

/// Store preferensi global.
final settingsStoreProvider = Provider<SettingsStore>((ref) => SettingsStore());

/// Mode tema reaktif — dibaca [EmasBerlianInsightApp], di-set dari Profil.
class ThemeModeController extends Notifier<ThemeMode> {
  @override
  ThemeMode build() => ref.read(settingsStoreProvider).themeMode;

  Future<void> set(ThemeMode mode) async {
    state = mode;
    await ref.read(settingsStoreProvider).setThemeMode(mode);
  }
}

/// Provider mode tema (Sistem/Terang/Gelap).
final themeModeProvider =
    NotifierProvider<ThemeModeController, ThemeMode>(ThemeModeController.new);
