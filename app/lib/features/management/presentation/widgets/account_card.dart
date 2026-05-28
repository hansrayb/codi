import 'package:flutter/material.dart';

import '../../../../theme/app_theme.dart';
import '../../domain/account.dart';
import 'role_badge.dart';

/// Kartu akun di S7 list.
class AccountCard extends StatelessWidget {
  const AccountCard({
    required this.account,
    this.onTap,
    super.key,
  });

  final ManagedAccount account;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.s16,
        vertical: AppSpacing.s4,
      ),
      child: Material(
        color: c.bgElev,
        borderRadius: BorderRadius.circular(AppRadius.r14),
        child: InkWell(
          borderRadius: BorderRadius.circular(AppRadius.r14),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.s14),
            child: Row(
              children: [
                _Avatar(initials: _initials(account.name), color: c),
                const SizedBox(width: AppSpacing.s12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Flexible(
                            child: Text(
                              account.name,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: AppTypography.bodyL.copyWith(
                                color: c.ink,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                          const SizedBox(width: AppSpacing.s8),
                          RoleBadge(account.role),
                        ],
                      ),
                      const SizedBox(height: 2),
                      Text(
                        account.email,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppTypography.bodyS.copyWith(
                          color: c.inkMuted,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.s4),
                      Row(
                        children: [
                          _StatusDot(active: account.isActive, color: c),
                          const SizedBox(width: AppSpacing.s4),
                          Text(
                            account.isActive ? 'aktif' : 'suspended',
                            style: AppTypography.labelS.copyWith(
                              color: account.isActive
                                  ? c.green
                                  : c.inkMuted,
                            ),
                          ),
                          if (account.lastLoginAt != null) ...[
                            const SizedBox(width: AppSpacing.s8),
                            Text(
                              '· ${_relTime(account.lastLoginAt!)}',
                              style: AppTypography.labelS.copyWith(
                                color: c.inkFaint,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ],
                  ),
                ),
                Icon(Icons.chevron_right, color: c.inkFaint, size: 20),
              ],
            ),
          ),
        ),
      ),
    );
  }

  static String _initials(String name) {
    final parts = name.trim().split(RegExp(r'\s+'));
    if (parts.isEmpty || parts.first.isEmpty) return '?';
    if (parts.length == 1) return parts.first.substring(0, 1).toUpperCase();
    return (parts.first[0] + parts.last[0]).toUpperCase();
  }

  static String _relTime(DateTime t) {
    final diff = DateTime.now().difference(t);
    if (diff.inMinutes < 1) return 'baru saja';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m lalu';
    if (diff.inHours < 24) return '${diff.inHours}j lalu';
    if (diff.inDays < 7) return '${diff.inDays}h lalu';
    return '${(diff.inDays / 7).floor()}mg lalu';
  }
}

class _Avatar extends StatelessWidget {
  const _Avatar({required this.initials, required this.color});

  final String initials;
  final AppColors color;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 44,
      height: 44,
      decoration: BoxDecoration(
        color: color.navySoft,
        shape: BoxShape.circle,
        border: Border.all(color: color.navyBlue.withValues(alpha: 0.3)),
      ),
      alignment: Alignment.center,
      child: Text(
        initials,
        style: AppTypography.bodyM.copyWith(
          color: color.navyBlue,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _StatusDot extends StatelessWidget {
  const _StatusDot({required this.active, required this.color});

  final bool active;
  final AppColors color;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 8,
      height: 8,
      decoration: BoxDecoration(
        color: active ? color.green : color.inkMuted,
        shape: BoxShape.circle,
      ),
    );
  }
}
