import 'package:flutter/material.dart';

import '../../auth/presentation/login_screen.dart';
import '../../chat/presentation/chat_screen.dart';
import '../../dashboard/presentation/dashboard_screen.dart';
import '../../insight/presentation/insight_screen.dart';
import '../../profile/presentation/profile_screen.dart';
import '../../reports/presentation/reports_screen.dart';
import 'widgets/bottom_nav.dart';

/// Host 4 tab utama + navigasi bottom nav fungsional.
///
/// Stack + `_TabLayer` agar state tiap tab tetap hidup saat pindah
/// (scroll, provider) — slide+fade transisi. 4 screen nyata: Beranda,
/// Insight, Laporan, Profil. FAB Codi → Chat via `push` (overlay
/// penuh). Routing `go_router` penuh = Fase 2 (`docs/07-ROADMAP.md`);
/// shell ini cukup untuk MVP.
class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  NavTab _tab = NavTab.beranda;

  static const _order = [
    NavTab.beranda,
    NavTab.insight,
    NavTab.laporan,
    NavTab.profil,
  ];

  int _prevIndex = 0;

  void _select(NavTab tab) {
    if (tab == _tab) return;
    setState(() {
      _prevIndex = _order.indexOf(_tab);
      _tab = tab;
    });
  }

  void _openChat() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => const ChatScreen()),
    );
  }

  /// Logout dari Profil → balik ke Login (replace stack). Login di-wire
  /// ulang: auth sukses → AppShell baru (sesi fresh).
  void _logout() {
    Navigator.of(context).pushReplacement(
      MaterialPageRoute<void>(
        builder: (ctx) => LoginScreen(
          onAuthenticated: () => Navigator.of(ctx).pushReplacement(
            MaterialPageRoute<void>(builder: (_) => const AppShell()),
          ),
        ),
      ),
    );
  }

  static const _fade = Duration(milliseconds: 200);

  @override
  Widget build(BuildContext context) {
    final active = _order.indexOf(_tab);
    // showBottomNav: false — navbar di-host shell (di luar _TabLayer)
    // supaya diam saat tab slide+fade. Cuma indikator active/inactive
    // BottomNav yang beranimasi internal.
    final pages = [
      DashboardScreen(
        onOpenChat: _openChat,
        onOpenInsight: () => _select(NavTab.insight),
        onNavTap: _select,
        showBottomNav: false,
      ),
      InsightScreen(
        onBack: () => _select(NavTab.beranda),
        onOpenChat: _openChat,
        onNavTap: _select,
        showBottomNav: false,
      ),
      ReportsScreen(
        onOpenChat: _openChat,
        onNavTap: _select,
        showBottomNav: false,
      ),
      ProfileScreen(
        onOpenChat: _openChat,
        onNavTap: _select,
        onLogout: _logout,
        showBottomNav: false,
      ),
    ];

    // Stack tab: crossfade+slide cepat, state tiap tab tetap hidup
    // (scroll/provider tak reset, seperti IndexedStack). Arah slide:
    // pindah ke index lebih besar → tab masuk dari kanan.
    final forward = active >= _prevIndex;

    // Scaffold di level shell — wajib agar Text punya Material ancestor
    // (tanpa ini muncul yellow debug underline). Tiap tab kini konten
    // saja, tak bawa Scaffold sendiri.
    return Scaffold(
      body: Stack(
        children: [
          for (var i = 0; i < pages.length; i++)
            _TabLayer(
              key: ValueKey(i),
              visible: i == active,
              forward: forward,
              duration: _fade,
              child: pages[i],
            ),
          // Navbar di-host shell — di luar _TabLayer, jadi tak ikut
          // animasi transisi tab.
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: BottomNav(
              active: _tab,
              onTap: _select,
              onFabTap: _openChat,
            ),
          ),
        ],
      ),
    );
  }
}

/// Satu layer tab — slide+fade cepat, nonaktif saat tersembunyi.
///
/// Visible: animasi ke (offset 0, opacity 1). Hidden: tetap di offset
/// geser + opacity 0 (state tab tetap hidup, tak rebuild).
class _TabLayer extends StatefulWidget {
  const _TabLayer({
    required this.visible,
    required this.forward,
    required this.duration,
    required this.child,
    super.key,
  });

  final bool visible;
  final bool forward;
  final Duration duration;
  final Widget child;

  @override
  State<_TabLayer> createState() => _TabLayerState();
}

class _TabLayerState extends State<_TabLayer>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl = AnimationController(
    vsync: this,
    duration: widget.duration,
    value: widget.visible ? 1 : 0,
  );

  @override
  void didUpdateWidget(_TabLayer old) {
    super.didUpdateWidget(old);
    if (widget.visible != old.visible) {
      widget.visible ? _ctrl.forward() : _ctrl.reverse();
    }
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Geser 6% lebar layar — cukup terasa, tetap cepat.
    final dx = MediaQuery.sizeOf(context).width * 0.06;
    final sign = widget.forward ? 1.0 : -1.0;
    final curve = CurvedAnimation(parent: _ctrl, curve: Curves.easeOutCubic);

    return AnimatedBuilder(
      animation: curve,
      builder: (context, child) {
        final t = curve.value; // 0 hidden → 1 visible
        return IgnorePointer(
          ignoring: !widget.visible,
          child: Opacity(
            opacity: t,
            child: Transform.translate(
              offset: Offset((1 - t) * dx * sign, 0),
              child: TickerMode(enabled: widget.visible, child: child!),
            ),
          ),
        );
      },
      child: widget.child,
    );
  }
}

