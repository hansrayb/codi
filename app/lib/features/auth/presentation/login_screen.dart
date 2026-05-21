import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
import '../../../widgets/emas_button.dart';
import '../application/auth_controller.dart';
import '../domain/auth_state.dart';
import 'widgets/login_logo.dart';

/// Login screen — layout match mockup `docs/emas-berlian-insight.html`
/// (`.login-screen`). Biometric auth, tanpa username/password
/// (`docs/06-SCREENS.md` S1).
///
/// Auth = mock in-memory (backend belum ada). On success: callback
/// [onAuthenticated] (routing di-wire saat go_router siap, Fase 1+).
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({this.onAuthenticated, super.key});

  /// Dipanggil saat login sukses (sementara: tampilkan placeholder).
  final VoidCallback? onAuthenticated;

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {

  @override
  Widget build(BuildContext context) {
    ref.listen<AuthState>(authControllerProvider, (prev, next) {
      if (next.status == LoginStatus.success) {
        widget.onAuthenticated?.call();
      }
    });

    final state = ref.watch(authControllerProvider);

    return Scaffold(
      body: DecoratedBox(
        decoration: BoxDecoration(
          gradient: RadialGradient(
            center: const Alignment(0, -0.5),
            radius: 1.1,
            colors: [const Color(0x2E4A7BC8), context.colors.bgApp],
            stops: const [0.0, 0.55],
          ),
        ),
        child: SafeArea(
          child: LayoutBuilder(
            builder: (context, constraints) {
              return SingleChildScrollView(
                child: ConstrainedBox(
                  constraints: BoxConstraints(
                    minHeight: constraints.maxHeight,
                  ),
                  child: IntrinsicHeight(
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(
                        AppSpacing.s32,
                        AppSpacing.s40,
                        AppSpacing.s32,
                        AppSpacing.s32,
                      ),
                      child: Column(
                        children: [
                          const SizedBox(height: AppSpacing.s40),
                          const LoginLogo(),
                          const SizedBox(height: AppSpacing.s24 + 4),
                          _brand(),
                          const SizedBox(height: AppSpacing.s8),
                          Text(
                            'Executive Business Intelligence',
                            textAlign: TextAlign.center,
                            style: AppTypography.bodyS.copyWith(
                              color: context.colors.inkMuted,
                              letterSpacing: 0.6,
                            ),
                          ),
                          const Spacer(),
                          _authArea(state),
                          const SizedBox(height: AppSpacing.s32),
                          _footer(),
                        ],
                      ),
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _brand() {
    return Text.rich(
      TextSpan(
        children: [
          const TextSpan(text: 'Emas Berlian '),
          TextSpan(
            text: 'Insight',
            style: AppTypography.headlineL.copyWith(
              color: context.colors.gold,
              fontStyle: FontStyle.italic,
            ),
          ),
        ],
      ),
      textAlign: TextAlign.center,
      style: AppTypography.headlineL.copyWith(fontSize: 26),
    );
  }

  Widget _authArea(AuthState state) {
    final busy = state.isBusy;

    return Column(
      children: [
        EmasButton(
          label: busy ? 'Memverifikasi...' : 'Masuk',
          icon: Icons.login,
          expand: true,
          onPressed: busy
              ? null
              : () =>
                  ref.read(authControllerProvider.notifier).loginDummy(),
        ),
        const SizedBox(height: AppSpacing.s12),
        Text(
          'Akses dummy — biometrik dinonaktifkan sementara',
          textAlign: TextAlign.center,
          style: AppTypography.bodyS.copyWith(
            color: context.colors.inkMuted,
          ),
        ),
      ],
    );
  }

  Widget _footer() {
    return Column(
      children: [
        Divider(color: context.colors.line, height: 1),
        const SizedBox(height: AppSpacing.s20),
        Text(
          'AKSES KHUSUS DIREKSI',
          textAlign: TextAlign.center,
          style: AppTypography.labelS.copyWith(color: context.colors.inkFaint),
        ),
        const SizedBox(height: AppSpacing.s4),
        Text(
          'v1.0.0 · 2026.05',
          textAlign: TextAlign.center,
          style: AppTypography.labelS.copyWith(color: context.colors.inkFaint),
        ),
      ],
    );
  }
}
