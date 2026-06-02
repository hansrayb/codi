import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api/repositories/auth_repository.dart';
import 'app.dart';
import 'providers/device_id_store.dart';
import 'providers/settings_store.dart';
import 'providers/token_store.dart';

/// Bangun `ProviderContainer` baru + muat store persist (token, deviceId,
/// settings) sebelum frame pertama.
///
/// [applyBootstrap] hanya `true` saat cold start. Saat logout JANGAN
/// re-inject bootstrap token — sesi harus benar-benar berakhir, bukan
/// auto-login ulang via `Env.bootstrapToken`.
Future<ProviderContainer> createAppContainer({
  bool applyBootstrap = false,
}) async {
  final container = ProviderContainer();
  final tokenStore = container.read(tokenStoreProvider);
  final deviceIdStore = container.read(deviceIdStoreProvider);
  final settingsStore = container.read(settingsStoreProvider);
  await Future.wait([
    tokenStore.load(),
    deviceIdStore.load(),
    settingsStore.load(),
  ]);
  if (applyBootstrap) {
    await applyBootstrapToken(tokenStore);
  }
  return container;
}

/// Root aplikasi yang memiliki [ProviderContainer] dan me-recreate-nya saat
/// logout.
///
/// Kenapa recreate, bukan sekadar navigasi ke Login: provider seperti
/// `chatControllerProvider` bersifat kept-alive (bukan autoDispose) di root
/// scope, jadi transkrip chat & data per-akun lain tetap hidup di memory
/// setelah logout dan bisa kelihatan saat akun lain login di device yang
/// sama. Mengganti container = wipe SEMUA state Riverpod sekaligus, anti
/// kebocoran data lintas-akun (sekarang & untuk provider baru di masa depan).
class AppBootstrap extends StatefulWidget {
  const AppBootstrap({required this.initialContainer, super.key});

  final ProviderContainer initialContainer;

  @override
  State<AppBootstrap> createState() => _AppBootstrapState();
}

class _AppBootstrapState extends State<AppBootstrap> {
  late ProviderContainer _container = widget.initialContainer;
  bool _busy = false;

  Future<void> _logout() async {
    if (_busy) return;
    _busy = true;
    // 1. Best-effort server logout + hapus token/kredensial dari storage
    //    (AuthRepository.logout sudah clear TokenStore di blok finally-nya).
    try {
      await _container.read(authRepositoryProvider).logout();
    } catch (_) {
      // Diabaikan — pembersihan lokal tetap jalan di repo.
    }
    // 2. Container baru = seluruh state Riverpod fresh. Tanpa bootstrap token
    //    supaya tidak auto-login lagi.
    final fresh = await createAppContainer();
    if (!mounted) {
      fresh.dispose();
      return;
    }
    final old = _container;
    setState(() {
      _container = fresh;
      _busy = false;
    });
    // Dispose container lama setelah frame berikutnya — beri waktu widget
    // lama lepas dari scope sebelum di-dispose.
    WidgetsBinding.instance.addPostFrameCallback((_) => old.dispose());
  }

  @override
  void dispose() {
    _container.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return UncontrolledProviderScope(
      key: ValueKey(_container),
      container: _container,
      child: EmasBerlianInsightApp(onLogout: _logout),
    );
  }
}
