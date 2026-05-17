import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
import '../application/auth_controller.dart';
import '../domain/auth_state.dart';
import 'widgets/biometric_button.dart';
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
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(authControllerProvider.notifier).checkAvailability();
    });
  }

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
    final locked = state.status == LoginStatus.locked;

    return Column(
      children: [
        BiometricButton(
          enabled: !busy && !locked,
          onTap: () =>
              ref.read(authControllerProvider.notifier).authenticate(),
        ),
        const SizedBox(height: AppSpacing.s12),
        Text(
          busy ? 'Memverifikasi...' : 'Sentuh untuk masuk',
          textAlign: TextAlign.center,
          style: AppTypography.bodyL.copyWith(color: context.colors.ink),
        ),
        const SizedBox(height: AppSpacing.s6),
        Text(
          state.errorMessage ?? 'Otentikasi biometrik diperlukan',
          textAlign: TextAlign.center,
          style: AppTypography.bodyS.copyWith(
            color: state.errorMessage != null
                ? context.colors.red
                : context.colors.inkMuted,
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
