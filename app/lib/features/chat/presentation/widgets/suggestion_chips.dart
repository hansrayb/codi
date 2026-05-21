import 'package:flutter/material.dart';

import '../../../../theme/app_theme.dart';

/// Suggestion chips (`docs/06-SCREENS.md` S3 → Suggestion Chips &
/// mockup `.suggestions`).
///
/// Scroll horizontal tanpa scrollbar, pill bgCard border line.
/// Tap → isi input chat.
class SuggestionChips extends StatelessWidget {
  const SuggestionChips({
    required this.suggestions,
    required this.onSelected,
    super.key,
  });

  final List<String> suggestions;
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) {
    if (suggestions.isEmpty) return const SizedBox.shrink();

    return SizedBox(
      height: 36,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.s16),
        itemCount: suggestions.length,
        separatorBuilder: (_, __) => const SizedBox(width: AppSpacing.s6),
        itemBuilder: (context, i) {
          final s = suggestions[i];
          return GestureDetector(
            onTap: () => onSelected(s),
            child: Container(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.s14,
                vertical: AppSpacing.s8,
              ),
              decoration: BoxDecoration(
                color: context.colors.bgCard,
                borderRadius: BorderRadius.circular(AppRadius.rPill),
                border: Border.all(color: context.colors.line),
              ),
              child: Text(
                s,
                style: AppTypography.bodyS.copyWith(
                  color: context.colors.inkDim,
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}
