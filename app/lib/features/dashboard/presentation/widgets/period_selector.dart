import 'package:flutter/material.dart';

import '../../../../theme/app_theme.dart';
import '../../domain/dashboard_state.dart';

/// Period selector (`docs/06-SCREENS.md` & mockup `.period-bar`).
///
/// Chip aktif: bg `goldSoft`, teks `gold`. On tap → [onChanged].
class PeriodSelector extends StatelessWidget {
  const PeriodSelector({
    required this.selected,
    required this.onChanged,
    super.key,
  });

  final Period selected;
  final ValueChanged<Period> onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.fromLTRB(
        AppSpacing.s20,
        0,
        AppSpacing.s20,
        AppSpacing.s16,
      ),
      padding: const EdgeInsets.all(AppSpacing.s6),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(AppRadius.r12),
        border: Border.all(color: AppColors.line),
      ),
      child: Row(
        children: [
          for (final p in Period.values)
            Expanded(
              child: GestureDetector(
                onTap: () => onChanged(p),
                behavior: HitTestBehavior.opaque,
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    vertical: AppSpacing.s8,
                  ),
                  decoration: BoxDecoration(
                    color: p == selected
                        ? AppColors.goldSoft
                        : Colors.transparent,
                    borderRadius: BorderRadius.circular(AppRadius.r8),
                  ),
                  child: Text(
                    p.label,
                    textAlign: TextAlign.center,
                    style: AppTypography.bodyS.copyWith(
                      color: p == selected
                          ? AppColors.gold
                          : AppColors.inkMuted,
                      fontWeight: p == selected
                          ? FontWeight.w600
                          : FontWeight.w500,
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
