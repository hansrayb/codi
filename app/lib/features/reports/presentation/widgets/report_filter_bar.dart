import 'package:flutter/material.dart';

import '../../../../models/report_item.dart';
import '../../../../theme/app_theme.dart';

/// Filter bar periode laporan (mockup `.filter-bar`).
///
/// Chip horizontal scroll, chip aktif = brand soft + border.
class ReportFilterBar extends StatelessWidget {
  const ReportFilterBar({
    required this.selected,
    required this.onChanged,
    super.key,
  });

  final ReportFilter selected;
  final ValueChanged<ReportFilter> onChanged;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 34,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.s20),
        itemCount: ReportFilter.values.length,
        separatorBuilder: (_, __) => const SizedBox(width: AppSpacing.s8),
        itemBuilder: (_, i) {
          final f = ReportFilter.values[i];
          return _Chip(
            label: f.label,
            active: f == selected,
            onTap: () => onChanged(f),
          );
        },
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  const _Chip({
    required this.label,
    required this.active,
    required this.onTap,
  });

  final String label;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.s14,
          vertical: AppSpacing.s8 - 1,
        ),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: active ? c.goldSoft : c.bgCard,
          borderRadius: BorderRadius.circular(AppRadius.rPill),
          border: Border.all(color: active ? c.goldLine : c.line),
        ),
        child: Text(
          label,
          style: AppTypography.labelM.copyWith(
            color: active ? c.gold : c.inkMuted,
            fontWeight: active ? FontWeight.w600 : FontWeight.w500,
          ),
        ),
      ),
    );
  }
}
