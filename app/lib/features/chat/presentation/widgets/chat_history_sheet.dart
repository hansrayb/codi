import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../../api/repositories/chat_repository.dart';
import '../../../../theme/app_theme.dart';

final _conversationsProvider =
    FutureProvider.autoDispose<List<ChatConversation>>((ref) {
  return ref.read(chatRepositoryProvider).getConversations();
});

/// Sheet Riwayat percakapan. Pilih satu → [onSelect] dengan conversation id.
Future<void> showChatHistorySheet(
  BuildContext context,
  void Function(String conversationId) onSelect,
) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (_) => _HistoryBody(onSelect: onSelect),
  );
}

class _HistoryBody extends ConsumerWidget {
  const _HistoryBody({required this.onSelect});

  final void Function(String conversationId) onSelect;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = context.colors;
    final async = ref.watch(_conversationsProvider);
    final maxH = MediaQuery.sizeOf(context).height * 0.8;
    return SafeArea(
      child: Container(
        constraints: BoxConstraints(maxHeight: maxH),
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
                Icon(Icons.history, size: 20, color: c.gold),
                const SizedBox(width: AppSpacing.s12),
                Text(
                  'Riwayat percakapan',
                  style: AppTypography.headlineS.copyWith(color: c.ink),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.s16),
            Flexible(
              child: async.when(
                loading: () => const Padding(
                  padding: EdgeInsets.symmetric(vertical: AppSpacing.s32),
                  child: Center(child: CircularProgressIndicator()),
                ),
                error: (e, _) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: AppSpacing.s24),
                  child: Text(
                    'Gagal memuat riwayat.\n$e',
                    textAlign: TextAlign.center,
                    style: AppTypography.bodyS.copyWith(color: c.red),
                  ),
                ),
                data: (convs) => convs.isEmpty
                    ? Padding(
                        padding: const EdgeInsets.symmetric(
                            vertical: AppSpacing.s24),
                        child: Text(
                          'Belum ada percakapan tersimpan.',
                          textAlign: TextAlign.center,
                          style:
                              AppTypography.bodyM.copyWith(color: c.inkMuted),
                        ),
                      )
                    : SingleChildScrollView(
                        child: Column(
                          children: [
                            for (var i = 0; i < convs.length; i++) ...[
                              if (i > 0) const SizedBox(height: AppSpacing.s8),
                              _ConvTile(
                                conv: convs[i],
                                onTap: () {
                                  Navigator.of(context).pop();
                                  onSelect(convs[i].id);
                                },
                              ),
                            ],
                          ],
                        ),
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ConvTile extends StatelessWidget {
  const _ConvTile({required this.conv, required this.onTap});

  final ChatConversation conv;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final when = conv.lastMessageAt == null
        ? ''
        : DateFormat('d MMM, HH:mm', 'id_ID').format(conv.lastMessageAt!);
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.s14),
        decoration: BoxDecoration(
          color: c.bgCard,
          borderRadius: BorderRadius.circular(AppRadius.r12),
          border: Border.all(color: c.line),
        ),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          conv.title.isNotEmpty ? conv.title : 'Percakapan',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: AppTypography.bodyL.copyWith(
                            color: c.ink,
                            fontWeight: FontWeight.w600,
                            fontSize: 13,
                          ),
                        ),
                      ),
                      if (when.isNotEmpty) ...[
                        const SizedBox(width: AppSpacing.s8),
                        Text(
                          when,
                          style:
                              AppTypography.bodyS.copyWith(color: c.inkFaint),
                        ),
                      ],
                    ],
                  ),
                  if (conv.preview.isNotEmpty) ...[
                    const SizedBox(height: 2),
                    Text(
                      conv.preview,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppTypography.bodyS
                          .copyWith(color: c.inkMuted, fontSize: 11),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(width: AppSpacing.s8),
            Icon(Icons.chevron_right, size: 18, color: c.inkFaint),
          ],
        ),
      ),
    );
  }
}
