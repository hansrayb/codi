import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Avatar inisial sesuai `docs/03-DESIGN-SYSTEM.md` (Avatar).
///
/// Gradient navy, border `goldLine`, inisial maks 2 char.
class EmasAvatar extends StatelessWidget {
  const EmasAvatar({
    required this.name,
    this.size = 40,
    super.key,
  });

  /// Nama sumber inisial.
  final String name;

  /// Diameter — default 40 (range 38-42).
  final double size;

  String get _initials {
    final parts = name.trim().split(RegExp(r'\s+'))
      ..removeWhere((p) => p.isEmpty);
    if (parts.isEmpty) return '?';
    if (parts.length == 1) {
      return parts.first.characters.take(2).toString().toUpperCase();
    }
    return (parts.first.characters.first + parts[1].characters.first)
        .toUpperCase();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [context.colors.navyBlue, const Color(0xFF2A4A7F)],
        ),
        border: Border.all(color: context.colors.goldLine),
      ),
      child: Text(
        _initials,
        style: AppTypography.labelM.copyWith(
          color: context.colors.ink,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
