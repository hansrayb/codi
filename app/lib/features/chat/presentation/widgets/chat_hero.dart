import 'package:flutter/material.dart';

import '../../../../theme/app_theme.dart';

/// Empty-state hero untuk Chat screen — gaya Claude AI:
/// headline besar "Pagi/Siang/Sore/Malam, <Nama>" dengan typewriter
/// animation, lalu prompt halus di bawahnya.
class ChatHero extends StatefulWidget {
  const ChatHero({required this.firstName, super.key});

  /// Nama panggilan user (dari TokenStore, biasanya first name).
  final String firstName;

  @override
  State<ChatHero> createState() => _ChatHeroState();
}

class _ChatHeroState extends State<ChatHero>
    with TickerProviderStateMixin {
  late final AnimationController _typeCtrl;
  late final AnimationController _fadeCtrl;
  late final String _greeting;
  late final String _prompt;

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _greeting = _greetingFor(now, widget.firstName);
    _prompt = _promptFor(now);

    // ~40ms per char untuk efek typewriter.
    final typeDuration =
        Duration(milliseconds: (_greeting.length * 40).clamp(600, 4000));
    _typeCtrl = AnimationController(vsync: this, duration: typeDuration)
      ..forward();
    _fadeCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 700),
    );
    // Fade-in prompt setelah typewriter selesai.
    _typeCtrl.addStatusListener((s) {
      if (s == AnimationStatus.completed && mounted) _fadeCtrl.forward();
    });
  }

  @override
  void dispose() {
    _typeCtrl.dispose();
    _fadeCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.s32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            AnimatedBuilder(
              animation: _typeCtrl,
              builder: (context, _) {
                final n = (_typeCtrl.value * _greeting.length).floor();
                final shown = _greeting.substring(0, n);
                final showCaret = _typeCtrl.status != AnimationStatus.completed;
                return RichText(
                  textAlign: TextAlign.center,
                  text: TextSpan(
                    style: AppTypography.headlineL.copyWith(
                      color: c.ink,
                      fontSize: 32,
                      height: 1.15,
                    ),
                    children: [
                      TextSpan(text: shown),
                      if (showCaret)
                        TextSpan(
                          text: '▍',
                          style: TextStyle(color: c.gold),
                        ),
                    ],
                  ),
                );
              },
            ),
            const SizedBox(height: AppSpacing.s16),
            FadeTransition(
              opacity: _fadeCtrl,
              child: Text(
                _prompt,
                textAlign: TextAlign.center,
                style: AppTypography.bodyM.copyWith(
                  color: c.inkMuted,
                  fontSize: 15,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  static String _greetingFor(DateTime now, String firstName) {
    final hour = now.hour;
    final label = hour < 11
        ? 'Pagi'
        : hour < 15
            ? 'Siang'
            : hour < 19
                ? 'Sore'
                : 'Malam';
    if (firstName.isEmpty) return '$label.';
    return '$label, $firstName';
  }

  static String _promptFor(DateTime now) {
    const prompts = [
      'Ada yang bisa saya bantu hari ini?',
      'Mau lihat ringkasan apa hari ini?',
      'Apa yang ingin kamu ketahui?',
      'Saya siap bantu — silakan tanya.',
      'Mulai dari mana hari ini?',
    ];
    return prompts[now.minute % prompts.length];
  }
}
