import 'package:flutter/material.dart';

import '../../../../theme/app_theme.dart';

enum _ChatMenu { baru, riwayat, salin, tentang }

/// Tombol menu `⋯` header chat (Percakapan baru / Riwayat / Salin / Tentang).
class ChatMenuButton extends StatelessWidget {
  const ChatMenuButton({
    required this.onNewChat,
    required this.onHistory,
    required this.onCopy,
    required this.onAbout,
    super.key,
  });

  final VoidCallback onNewChat;
  final VoidCallback onHistory;
  final VoidCallback onCopy;
  final VoidCallback onAbout;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return PopupMenuButton<_ChatMenu>(
      tooltip: 'Menu',
      color: c.bgElev,
      icon: Icon(Icons.more_horiz, size: 20, color: c.inkDim),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadius.r12),
        side: BorderSide(color: c.line),
      ),
      onSelected: (v) {
        switch (v) {
          case _ChatMenu.baru:
            onNewChat();
          case _ChatMenu.riwayat:
            onHistory();
          case _ChatMenu.salin:
            onCopy();
          case _ChatMenu.tentang:
            onAbout();
        }
      },
      itemBuilder: (context) => [
        _item(context, _ChatMenu.baru, Icons.add_comment_outlined,
            'Percakapan baru'),
        _item(context, _ChatMenu.riwayat, Icons.history, 'Riwayat percakapan'),
        _item(context, _ChatMenu.salin, Icons.copy_outlined,
            'Salin percakapan'),
        _item(context, _ChatMenu.tentang, Icons.info_outline, 'Tentang Codi'),
      ],
    );
  }

  PopupMenuItem<_ChatMenu> _item(
    BuildContext context,
    _ChatMenu value,
    IconData icon,
    String label,
  ) {
    final c = context.colors;
    return PopupMenuItem<_ChatMenu>(
      value: value,
      child: Row(
        children: [
          Icon(icon, size: 18, color: c.inkDim),
          const SizedBox(width: AppSpacing.s12),
          Flexible(
            child: Text(label, style: AppTypography.bodyM.copyWith(color: c.ink)),
          ),
        ],
      ),
    );
  }
}

/// Sheet "Tentang Codi" — apa itu Codi di konteks chat ini.
Future<void> showCodiAboutSheet(BuildContext context) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => const _CodiAboutBody(),
  );
}

class _CodiAboutBody extends StatelessWidget {
  const _CodiAboutBody();

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return SafeArea(
      child: Container(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.s20,
          AppSpacing.s12,
          AppSpacing.s20,
          AppSpacing.s20,
        ),
        decoration: BoxDecoration(
          color: c.bgApp,
          borderRadius: const BorderRadius.vertical(
            top: Radius.circular(AppRadius.r20),
          ),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: Container(
                width: 36,
                height: 4,
                decoration: BoxDecoration(
                  color: c.line,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.s16),
            Row(
              children: [
                Container(
                  width: 42,
                  height: 42,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: c.goldSoft,
                    borderRadius: BorderRadius.circular(AppRadius.r12),
                    border: Border.all(color: c.goldLine),
                  ),
                  child: Icon(Icons.auto_awesome, size: 20, color: c.gold),
                ),
                const SizedBox(width: AppSpacing.s14),
                Expanded(
                  child: Text(
                    'Tentang Codi',
                    style: AppTypography.headlineS.copyWith(color: c.ink),
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.s16),
            Text(
              'Codi adalah asisten eksekutif kamu — terhubung langsung ke '
              'sistem operasional (Lumbung, HR/payroll) untuk menjawab '
              'pertanyaan dengan data nyata.',
              style: AppTypography.bodyM.copyWith(color: c.inkMuted),
            ),
            const SizedBox(height: AppSpacing.s14),
            const _Row(label: 'Mode', value: 'Penasihat (advisor)'),
            const _Row(label: 'Akses', value: 'Read-only · analitik'),
            const _Row(label: 'Respon', value: 'Real-time streaming'),
            const SizedBox(height: AppSpacing.s14),
            Text(
              'Pesan kamu diproses oleh orchestrator Codi di server. '
              'Codi tidak mengubah data dari layar chat ini.',
              style: AppTypography.bodyS.copyWith(color: c.inkFaint),
            ),
          ],
        ),
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.s8),
      child: Row(
        children: [
          SizedBox(
            width: 80,
            child: Text(
              label,
              style: AppTypography.bodyS.copyWith(color: c.inkMuted),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: AppTypography.bodyM.copyWith(
                color: c.ink,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
