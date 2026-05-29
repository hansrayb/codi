import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
import '../../../widgets/emas_button.dart';
import '../../../widgets/emas_input.dart';
import '../application/auth_controller.dart';
import '../domain/auth_state.dart';
import 'widgets/biometric_button.dart';
import 'widgets/login_logo.dart';
import 'widgets/tech_backdrop.dart';

/// Login screen — dual mode email/biometric (`docs/06-SCREENS.md` S1).
///
/// Mode email: form email + password → `POST /auth/login` → auto-enroll.
/// Mode biometric: tap → `POST /auth/login-biometric`.
/// Mode dipilih otomatis berdasarkan flag `hasEnrolledBiometric` lokal.
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({this.onAuthenticated, super.key});

  /// Dipanggil saat login sukses.
  final VoidCallback? onAuthenticated;

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  late final TextEditingController _passwordCtrl;
  late final TextEditingController _emailCtrl;

  @override
  void initState() {
    super.initState();
    final initialEmail = ref.read(authControllerProvider).email;
    _emailCtrl = TextEditingController(text: initialEmail);
    _passwordCtrl = TextEditingController();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(authControllerProvider.notifier).checkAvailability();
    });
  }

  @override
  void dispose() {
    _emailCtrl.dispose();
    _passwordCtrl.dispose();
    super.dispose();
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
      body: Stack(
        children: [
          Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: RadialGradient(
                  center: const Alignment(0, -0.5),
                  radius: 1.1,
                  colors: [const Color(0x2E4A7BC8), context.colors.bgApp],
                  stops: const [0.0, 0.55],
                ),
              ),
            ),
          ),
          Positioned.fill(child: TechBackdrop(color: context.colors.gold)),
          SafeArea(
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
                          AppSpacing.s32,
                          AppSpacing.s32,
                          AppSpacing.s24,
                        ),
                        child: TweenAnimationBuilder<double>(
                          tween: Tween(begin: 0.0, end: 1.0),
                          duration: const Duration(milliseconds: 700),
                          curve: Curves.easeOut,
                          builder: (context, v, child) => Opacity(
                            opacity: v.clamp(0.0, 1.0),
                            child: Transform.translate(
                              offset: Offset(0, (1 - v) * 14),
                              child: child,
                            ),
                          ),
                          child: Column(
                            children: [
                              const SizedBox(height: AppSpacing.s32),
                              const LoginLogo(),
                              const SizedBox(height: AppSpacing.s24),
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
                              const SizedBox(height: AppSpacing.s24),
                              _footer(),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        ],
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
    if (state.mode == LoginMode.biometric) {
      return _biometricArea(state);
    }
    return _emailArea(state);
  }

  Widget _emailArea(AuthState state) {
    final ctrl = ref.read(authControllerProvider.notifier);
    final busy = state.isBusy;
    final hasError = (state.errorMessage ?? '').isNotEmpty;
    final canShowBiometricSwitch =
        state.biometricAvailable && state.hasEnrolledBiometric;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        EmasInput(
          controller: _emailCtrl,
          hintText: 'Email direksi',
          onChanged: ctrl.setEmail,
        ),
        const SizedBox(height: AppSpacing.s12),
        EmasInput(
          controller: _passwordCtrl,
          hintText: 'Password',
          obscureText: true,
        ),
        const SizedBox(height: AppSpacing.s16),
        EmasButton(
          label: busy ? 'Memverifikasi...' : 'Masuk',
          icon: Icons.login,
          expand: true,
          onPressed: busy
              ? null
              : () => ctrl.loginEmail(password: _passwordCtrl.text),
        ),
        if (hasError) ...[
          const SizedBox(height: AppSpacing.s12),
          Text(
            state.errorMessage!,
            textAlign: TextAlign.center,
            style: AppTypography.bodyS.copyWith(color: context.colors.red),
          ),
        ],
        if (canShowBiometricSwitch) ...[
          const SizedBox(height: AppSpacing.s16),
          TextButton.icon(
            onPressed: busy ? null : () => ctrl.switchMode(LoginMode.biometric),
            icon: Icon(Icons.fingerprint, color: context.colors.gold),
            label: Text(
              'Pakai biometric',
              style: AppTypography.bodyS.copyWith(color: context.colors.gold),
            ),
          ),
        ],
      ],
    );
  }

  Widget _biometricArea(AuthState state) {
    final ctrl = ref.read(authControllerProvider.notifier);
    final busy = state.isBusy;
    final disabled = state.status == LoginStatus.locked;
    final error = state.errorMessage;
    final hasError = error != null && error.isNotEmpty;

    return Column(
      children: [
        BiometricButton(
          enabled: !busy && !disabled,
          onTap: () => ctrl.loginBiometric(),
        ),
        const SizedBox(height: AppSpacing.s20),
        Text(
          busy ? 'Memverifikasi...' : 'Sentuh untuk masuk',
          textAlign: TextAlign.center,
          style: AppTypography.bodyM.copyWith(
            color: context.colors.ink,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: AppSpacing.s4),
        if (hasError)
          Text(
            error,
            textAlign: TextAlign.center,
            style: AppTypography.bodyS.copyWith(color: context.colors.red),
          )
        else
          Text(
            'Gunakan Face ID atau sidik jari',
            textAlign: TextAlign.center,
            style: AppTypography.bodyS.copyWith(color: context.colors.inkMuted),
          ),
        const SizedBox(height: AppSpacing.s16),
        TextButton.icon(
          onPressed: busy ? null : () => ctrl.switchMode(LoginMode.email),
          icon: Icon(Icons.mail_outline, color: context.colors.gold),
          label: Text(
            'Pakai email',
            style: AppTypography.bodyS.copyWith(color: context.colors.gold),
          ),
        ),
      ],
    );
  }

  Widget _footer() {
    return Column(
      children: [
        Divider(color: context.colors.line, height: 1),
        const SizedBox(height: AppSpacing.s16),
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
