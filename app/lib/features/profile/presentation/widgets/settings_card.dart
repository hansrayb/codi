import 'package:flutter/material.dart';

import '../../../../models/profile_data.dart';
import '../../../../theme/app_theme.dart';

/// Grup pengaturan: label + card berisi rows (mockup `.settings-group`).
class SettingsGroupView extends StatelessWidget {
  const SettingsGroupView({
    required this.group,
    required this.onTapItem,
    required this.onToggle,
    this.iconFor,
    super.key,
  });

  final SettingsGroup group;

  /// Tap row tipe chevron/value.
  final ValueChanged<String> onTapItem;

  /// Toggle row tipe toggle.
  final ValueChanged<String> onToggle;

  /// Ikon per item id (opsional — fallback ke ikon generik).
  final IconData Function(String id)? iconFor;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.s20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.s4,
              AppSpacing.s16,
              AppSpacing.s4,
              AppSpacing.s8,
            ),
            child: Text(
              group.label.toUpperCase(),
              style: AppTypography.labelS.copyWith(
                color: c.inkMuted,
                fontSize: 10,
              ),
            ),
          ),
          Container(
            decoration: BoxDecoration(
              color: c.bgCard,
              borderRadius: BorderRadius.circular(AppRadius.r16),
              border: Border.all(color: c.line),
            ),
            child: Column(
              children: [
                for (var i = 0; i < group.items.length; i++)
                  _Row(
                    item: group.items[i],
                    isLast: i == group.items.length - 1,
                    icon: iconFor?.call(group.items[i].id) ??
                        Icons.settings_outlined,
                    onTap: () => onTapItem(group.items[i].id),
                    onToggle: () => onToggle(group.items[i].id),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({
    required this.item,
    required this.isLast,
    required this.icon,
    required this.onTap,
    required this.onToggle,
  });

  final SettingsItem item;
  final bool isLast;
  final IconData icon;
  final VoidCallback onTap;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final isToggle = item.trailing == SettingsTrailing.toggle;
    return GestureDetector(
      onTap: isToggle ? onToggle : onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.s16,
          vertical: AppSpacing.s14,
        ),
        decoration: BoxDecoration(
          border: isLast
              ? null
              : Border(bottom: BorderSide(color: c.line)),
        ),
        child: Row(
          children: [
            Container(
              width: 32,
              height: 32,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: c.bgElev,
                borderRadius: BorderRadius.circular(AppRadius.r8 + 1),
              ),
              child: Icon(icon, size: 16, color: c.inkDim),
            ),
            const SizedBox(width: AppSpacing.s12 + 1),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.title,
                    style: AppTypography.bodyL.copyWith(
                      color: c.ink,
                      fontWeight: FontWeight.w500,
                      fontSize: 13,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.s2),
                  Text(
                    item.subtitle,
                    style: AppTypography.bodyS.copyWith(
                      color: c.inkMuted,
                      fontSize: 11,
                    ),
                  ),
                ],
              ),
            ),
            _trailing(context),
          ],
        ),
      ),
    );
  }

  Widget _trailing(BuildContext context) {
    final c = context.colors;
    switch (item.trailing) {
      case SettingsTrailing.toggle:
        return _Toggle(on: item.toggleOn);
      case SettingsTrailing.value:
        return Row(
          children: [
            Text(
              item.value ?? '',
              style: AppTypography.bodyS.copyWith(
                color: c.inkMuted,
                fontSize: 12,
              ),
            ),
            const SizedBox(width: AppSpacing.s6),
            Icon(Icons.chevron_right, size: 16, color: c.inkFaint),
          ],
        );
      case SettingsTrailing.chevron:
        return Icon(Icons.chevron_right, size: 16, color: c.inkFaint);
    }
  }
}

/// Toggle pill (mockup `.toggle` / `.toggle.on`).
class _Toggle extends StatelessWidget {
  const _Toggle({required this.on});

  final bool on;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      curve: Curves.easeOut,
      width: 40,
      height: 23,
      decoration: BoxDecoration(
        color: on ? c.goldSoft : c.bgElev,
        borderRadius: BorderRadius.circular(AppRadius.rPill),
        border: Border.all(color: on ? c.goldLine : c.lineStrong),
      ),
      child: AnimatedAlign(
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOut,
        alignment: on ? Alignment.centerRight : Alignment.centerLeft,
        child: Container(
          margin: const EdgeInsets.all(2),
          width: 17,
          height: 17,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: on ? c.gold : c.inkMuted,
          ),
        ),
      ),
    );
  }
}
