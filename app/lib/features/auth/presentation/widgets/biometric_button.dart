import 'package:flutter/material.dart';

import '../../../../theme/app_theme.dart';

/// Tombol biometric sesuai mockup `docs/emas-berlian-insight.html`
/// (`.biometric-btn`).
///
/// Lingkaran 88px, gradient navy, border `navyBlue`. Pulse ring animasi
/// 2.4s infinite (scale 1 → 1.35, opacity 0.35 → 0) — CSS `pulse-ring`.
class BiometricButton extends StatefulWidget {
  const BiometricButton({
    required this.onTap,
    this.enabled = true,
    super.key,
  });

  /// Callback saat di-tap.
  final VoidCallback onTap;

  /// Pulse + tap aktif jika true.
  final bool enabled;

  @override
  State<BiometricButton> createState() => _BiometricButtonState();
}

class _BiometricButtonState extends State<BiometricButton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  static const double _size = 88;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2400),
    );
    if (widget.enabled) _controller.repeat();
  }

  @override
  void didUpdateWidget(BiometricButton oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.enabled && !_controller.isAnimating) {
      _controller.repeat();
    } else if (!widget.enabled && _controller.isAnimating) {
      _controller.stop();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: _size + 32,
      height: _size + 32,
      child: Stack(
        alignment: Alignment.center,
        children: [
          if (widget.enabled)
            AnimatedBuilder(
              animation: _controller,
              builder: (context, child) {
                final t = _controller.value;
                final scale = 1.0 + (0.35 * t);
                final opacity = (0.35 * (1 - t)).clamp(0.0, 1.0);
                return Transform.scale(
                  scale: scale,
                  child: Container(
                    width: _size + 16,
                    height: _size + 16,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: AppColors.navyBlue.withValues(alpha: opacity),
                      ),
                    ),
                  ),
                );
              },
            ),
          GestureDetector(
            onTap: widget.enabled ? widget.onTap : null,
            child: Container(
              width: _size,
              height: _size,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: const LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [AppColors.navySoft, Color(0x0A4A7BC8)],
                ),
                border: Border.all(color: AppColors.navyBlue),
              ),
              child: const Icon(
                Icons.fingerprint,
                size: 40,
                color: AppColors.navyBlue,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
