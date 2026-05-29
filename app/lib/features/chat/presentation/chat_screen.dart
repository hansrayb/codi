import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/chat_message.dart';
import '../../../providers/token_store.dart';
import '../../../theme/app_theme.dart';
import '../application/chat_controller.dart';
import 'widgets/chat_history_sheet.dart';
import 'widgets/chat_menu.dart';
import 'widgets/chat_hero.dart';
import 'widgets/chat_input.dart';
import 'widgets/codi_avatar.dart';
import 'widgets/message_bubble.dart';
import 'widgets/suggestion_chips.dart';

/// Chat screen (`docs/06-SCREENS.md` S3, layout match mockup
/// `docs/emas-berlian-insight.html` `.chat-screen`).
///
/// Header (back, Codi avatar, status), messages auto-scroll, suggestion
/// chips, input. Mock conversation + canned reply.
class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _inputController = TextEditingController();
  final _scrollController = ScrollController();

  @override
  void dispose() {
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOutCubic,
      );
    });
  }

  Future<void> _send(String text) async {
    _scrollToBottom();
    await ref.read(chatControllerProvider.notifier).send(text);
    _scrollToBottom();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(chatControllerProvider);
    final isEmpty = state.messages.isEmpty;
    final store = ref.read(tokenStoreProvider);
    final firstName = store.name.isNotEmpty ? store.name.split(' ').first : '';

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            _header(state.isSending),
            Expanded(
              child: isEmpty
                  ? ChatHero(firstName: firstName)
                  : ListView.builder(
                      controller: _scrollController,
                      padding: const EdgeInsets.fromLTRB(
                        AppSpacing.s16,
                        AppSpacing.s16,
                        AppSpacing.s16,
                        AppSpacing.s8,
                      ),
                      itemCount: state.messages.length + 1,
                      itemBuilder: (context, i) {
                        if (i == 0) return const _DayMarker();
                        final msg = state.messages[i - 1];
                        return MessageBubble(message: msg);
                      },
                    ),
            ),
            if (state.isSending) const _TypingIndicator(),
            SuggestionChips(
              suggestions: state.suggestions,
              onSelected: (s) => _inputController.text = s,
            ),
            ChatInput(
              controller: _inputController,
              enabled: !state.isSending,
              onSend: _send,
            ),
          ],
        ),
      ),
    );
  }

  Widget _header(bool busy) {
    return Container(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.s20,
        AppSpacing.s8,
        AppSpacing.s20,
        AppSpacing.s14,
      ),
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: context.colors.line)),
      ),
      child: Row(
        children: [
          GestureDetector(
            onTap: () => Navigator.of(context).maybePop(),
            child: SizedBox(
              width: 32,
              height: 32,
              child: Icon(
                Icons.arrow_back,
                size: 20,
                color: context.colors.inkDim,
              ),
            ),
          ),
          const SizedBox(width: AppSpacing.s12),
          const CodiAvatar(),
          const SizedBox(width: AppSpacing.s12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Codi', style: AppTypography.headlineS),
                const SizedBox(height: 1),
                Row(
                  children: [
                    Container(
                      width: 5,
                      height: 5,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: context.colors.green,
                      ),
                    ),
                    const SizedBox(width: AppSpacing.s4),
                    Text(
                      busy ? 'Mengetik...' : 'Aktif · respon 0,8s',
                      style: AppTypography.bodyS.copyWith(
                        color: context.colors.green,
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          ChatMenuButton(
            onNewChat: _confirmNewChat,
            onHistory: () => showChatHistorySheet(
              context,
              (id) =>
                  ref.read(chatControllerProvider.notifier).loadConversation(id),
              onDeleted: (id) {
                if (ref.read(chatControllerProvider).conversationId == id) {
                  ref.read(chatControllerProvider.notifier).reset();
                }
              },
            ),
            onCopy: _copyTranscript,
            onAbout: () => showCodiAboutSheet(context),
          ),
        ],
      ),
    );
  }

  Future<void> _confirmNewChat() async {
    final ctrl = ref.read(chatControllerProvider.notifier);
    final hasMessages = ref.read(chatControllerProvider).messages.isNotEmpty;
    if (!hasMessages) {
      ctrl.reset();
      return;
    }
    final c = context.colors;
    final yes = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: c.bgElev,
        title: Text('Percakapan baru?', style: AppTypography.headlineS),
        content: Text(
          'Percakapan saat ini akan dikosongkan dari layar.',
          style: AppTypography.bodyM.copyWith(color: c.inkMuted),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Batal'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Mulai baru'),
          ),
        ],
      ),
    );
    if (yes == true) ctrl.reset();
  }

  void _copyTranscript() {
    final messages = ref.read(chatControllerProvider).messages;
    if (messages.isEmpty) {
      _snack('Belum ada percakapan untuk disalin.');
      return;
    }
    final transcript = messages
        .map((m) =>
            '${m.sender == MessageSender.user ? 'Saya' : 'Codi'}: ${m.text}')
        .join('\n\n');
    Clipboard.setData(ClipboardData(text: transcript));
    _snack('Percakapan disalin.');
  }

  void _snack(String text) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(text)));
  }
}

class _DayMarker extends StatelessWidget {
  const _DayMarker();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.s14),
      child: Center(
        child: Text(
          'HARI INI · 09:42',
          style: AppTypography.labelS.copyWith(color: context.colors.inkFaint),
        ),
      ),
    );
  }
}

class _TypingIndicator extends StatelessWidget {
  const _TypingIndicator();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.s20,
        vertical: AppSpacing.s4,
      ),
      child: Row(
        children: [
          SizedBox(
            width: 14,
            height: 14,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              color: context.colors.gold,
            ),
          ),
          const SizedBox(width: AppSpacing.s8),
          Text(
            'Codi sedang menyiapkan jawaban...',
            style: AppTypography.bodyS.copyWith(color: context.colors.inkMuted),
          ),
        ],
      ),
    );
  }
}
