import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Bentuk input sesuai `docs/03-DESIGN-SYSTEM.md` (Input → Text Input).
enum EmasInputShape {
  /// `radiusPill` — dipakai chat input.
  pill,

  /// `radius12` — dipakai form.
  form,
}

/// Text input Emas Berlian Insight.
///
/// Background `bgInput`, border `lineStrong`, focus → border `gold`.
class EmasInput extends StatelessWidget {
  const EmasInput({
    this.controller,
    this.hintText,
    this.shape = EmasInputShape.form,
    this.onChanged,
    this.onSubmitted,
    this.obscureText = false,
    this.maxLines = 1,
    this.suffix,
    super.key,
  });

  /// Controller teks (opsional).
  final TextEditingController? controller;

  /// Placeholder.
  final String? hintText;

  /// Bentuk border.
  final EmasInputShape shape;

  /// Callback perubahan teks.
  final ValueChanged<String>? onChanged;

  /// Callback submit (enter/done).
  final ValueChanged<String>? onSubmitted;

  /// Sembunyikan teks (password).
  final bool obscureText;

  /// Maks baris.
  final int maxLines;

  /// Widget di kanan input (mis. tombol kirim).
  final Widget? suffix;

  double get _radius =>
      shape == EmasInputShape.pill ? AppRadius.rPill : AppRadius.r12;

  @override
  Widget build(BuildContext context) {
    final border = OutlineInputBorder(
      borderRadius: BorderRadius.circular(_radius),
      borderSide: BorderSide(color: context.colors.lineStrong),
    );

    return TextField(
      controller: controller,
      onChanged: onChanged,
      onSubmitted: onSubmitted,
      obscureText: obscureText,
      maxLines: maxLines,
      style: AppTypography.bodyM.copyWith(color: context.colors.ink),
      cursorColor: context.colors.gold,
      decoration: InputDecoration(
        filled: true,
        fillColor: context.colors.bgInput,
        hintText: hintText,
        hintStyle: AppTypography.bodyM.copyWith(color: context.colors.inkFaint),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.s16,
          vertical: AppSpacing.s8,
        ),
        suffixIcon: suffix,
        border: border,
        enabledBorder: border,
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(_radius),
          borderSide: BorderSide(color: context.colors.gold),
        ),
      ),
    );
  }
}
