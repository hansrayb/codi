import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Variant tombol sesuai `docs/03-DESIGN-SYSTEM.md` (Buttons).
enum EmasButtonVariant {
  /// Gold gradient, teks gelap. CTA utama.
  primary,

  /// Transparan, border `lineStrong`, teks `ink`.
  secondary,

  /// Teks `gold` saja, tanpa border/background.
  ghost,
}

/// Tombol Emas Berlian Insight — 3 variant.
///
/// Pressed: scale 0.97 + opacity 0.9 (micro 150ms easeOutCubic,
/// `docs/03-DESIGN-SYSTEM.md` → Animation).
class EmasButton extends StatefulWidget {
  const EmasButton({
    required this.label,
    required this.onPressed,
    this.variant = EmasButtonVariant.primary,
    this.icon,
    this.expand = false,
    super.key,
  });

  /// Teks tombol.
  final String label;

  /// Callback. Null = disabled (opacity turun, tak bisa tap).
  final VoidCallback? onPressed;

  /// Variant visual.
  final EmasButtonVariant variant;

  /// Ikon opsional di kiri label.
  final IconData? icon;

  /// Lebar penuh parent jika true.
  final bool expand;

  @override
  State<EmasButton> createState() => _EmasButtonState();
}

class _EmasButtonState extends State<EmasButton> {
  bool _pressed = false;

  bool get _enabled => widget.onPressed != null;

  void _setPressed(bool value) {
    if (!_enabled) return;
    setState(() => _pressed = value);
  }

  @override
  Widget build(BuildContext context) {
    return Opacity(
      opacity: _enabled ? 1.0 : 0.45,
      child: GestureDetector(
        onTapDown: (_) => _setPressed(true),
        onTapUp: (_) => _setPressed(false),
        onTapCancel: () => _setPressed(false),
        onTap: widget.onPressed,
        child: AnimatedScale(
          scale: _pressed ? 0.97 : 1.0,
          duration: const Duration(milliseconds: 150),
          curve: Curves.easeOutCubic,
          child: AnimatedOpacity(
            opacity: _pressed ? 0.9 : 1.0,
            duration: const Duration(milliseconds: 150),
            child: _buildBody(),
          ),
        ),
      ),
    );
  }

  Widget _buildBody() {
    switch (widget.variant) {
      case EmasButtonVariant.primary:
        return _container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [context.colors.goldBright, context.colors.gold],
            ),
            borderRadius: BorderRadius.circular(AppRadius.r14),
            boxShadow: AppElevation.elev2,
          ),
          foreground: context.colors.bgApp,
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.s14,
            vertical: AppSpacing.s12,
          ),
        );
      case EmasButtonVariant.secondary:
        return _container(
          decoration: BoxDecoration(
            color: _pressed ? context.colors.bgHighlight : Colors.transparent,
            borderRadius: BorderRadius.circular(AppRadius.r14),
            border: Border.all(color: context.colors.lineStrong),
          ),
          foreground: context.colors.ink,
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.s14,
            vertical: AppSpacing.s12,
          ),
        );
      case EmasButtonVariant.ghost:
        return _container(
          decoration: const BoxDecoration(),
          foreground: context.colors.gold,
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.s8,
            vertical: AppSpacing.s6,
          ),
        );
    }
  }

  Widget _container({
    required BoxDecoration decoration,
    required Color foreground,
    required EdgeInsetsGeometry padding,
  }) {
    final content = Row(
      mainAxisSize: widget.expand ? MainAxisSize.max : MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        if (widget.icon != null) ...[
          Icon(widget.icon, size: 16, color: foreground),
          const SizedBox(width: AppSpacing.s6),
        ],
        Text(
          widget.label,
          style: AppTypography.labelM.copyWith(
            color: foreground,
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );

    return Container(
      padding: padding,
      decoration: decoration,
      child: content,
    );
  }
}
