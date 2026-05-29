import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:intl/intl.dart';

import '../../../../models/chat_message.dart';
import '../../../../theme/app_theme.dart';
import 'rich_card.dart';

/// Bubble pesan (`docs/06-SCREENS.md` S3 → Messages & mockup `.msg`).
///
/// User: align kanan, gradient navy, border goldLine, sudut kanan-bawah
/// 4px. Bot: align kiri, bgCard, sudut kiri-bawah 4px, optional rich card.
class MessageBubble extends StatelessWidget {
  const MessageBubble({
    required this.message,
    this.onAction,
    super.key,
  });

  final ChatMessage message;

  /// Callback aksi rich card.
  final ValueChanged<RichAction>? onAction;

  @override
  Widget build(BuildContext context) {
    final isUser = message.isUser;
    final time = DateFormat('HH:mm').format(message.time);
    final timeText = message.responSeconds != null
        ? '$time · ${message.responSeconds.toString().replaceAll('.', ',')}s'
        : time;

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.86,
        ),
        child: Container(
          margin: const EdgeInsets.only(bottom: AppSpacing.s14),
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.s14,
            vertical: AppSpacing.s12,
          ),
          decoration: BoxDecoration(
            gradient: isUser
                ? LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      context.colors.navyBlue,
                      const Color(0xFF2A4A7F),
                    ],
                  )
                : null,
            color: isUser ? null : context.colors.bgCard,
            border: Border.all(
              color: isUser ? context.colors.goldLine : context.colors.line,
            ),
            borderRadius: BorderRadius.only(
              topLeft: const Radius.circular(AppRadius.r18),
              topRight: const Radius.circular(AppRadius.r18),
              bottomLeft: Radius.circular(
                isUser ? AppRadius.r18 : AppRadius.r4,
              ),
              bottomRight: Radius.circular(
                isUser ? AppRadius.r4 : AppRadius.r18,
              ),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (isUser)
                Text(
                  message.text,
                  style: AppTypography.bodyM.copyWith(
                    color: context.colors.ink,
                    fontWeight: FontWeight.w500,
                    height: 1.5,
                  ),
                )
              else
                MarkdownBody(
                  data: message.text,
                  selectable: true,
                  shrinkWrap: true,
                  styleSheet: MarkdownStyleSheet(
                    p: AppTypography.bodyM.copyWith(
                      color: context.colors.ink,
                      height: 1.5,
                    ),
                    strong: AppTypography.bodyM.copyWith(
                      color: context.colors.ink,
                      fontWeight: FontWeight.w700,
                      height: 1.5,
                    ),
                    em: AppTypography.bodyM.copyWith(
                      color: context.colors.ink,
                      fontStyle: FontStyle.italic,
                      height: 1.5,
                    ),
                    h1: AppTypography.headlineS.copyWith(color: context.colors.ink),
                    h2: AppTypography.headlineS.copyWith(
                      color: context.colors.ink,
                      fontSize: 16,
                    ),
                    h3: AppTypography.bodyL.copyWith(
                      color: context.colors.ink,
                      fontWeight: FontWeight.w700,
                    ),
                    listBullet: AppTypography.bodyM.copyWith(
                      color: context.colors.gold,
                    ),
                    code: TextStyle(
                      fontFamily: 'monospace',
                      backgroundColor: context.colors.bgInput,
                      color: context.colors.gold,
                    ),
                    codeblockDecoration: BoxDecoration(
                      color: context.colors.bgInput,
                      borderRadius: BorderRadius.circular(AppRadius.r8),
                    ),
                    blockquote: AppTypography.bodyM.copyWith(
                      color: context.colors.inkMuted,
                      fontStyle: FontStyle.italic,
                    ),
                    tableHead: AppTypography.bodyS.copyWith(
                      color: context.colors.ink,
                      fontWeight: FontWeight.w700,
                    ),
                    tableBody: AppTypography.bodyS.copyWith(
                      color: context.colors.ink,
                    ),
                    tableBorder: TableBorder.all(
                      color: context.colors.line,
                    ),
                  ),
                ),
              if (message.card != null) ...[
                const SizedBox(height: AppSpacing.s8),
                RichCardView(card: message.card!, onAction: onAction),
              ],
              const SizedBox(height: AppSpacing.s4),
              Align(
                alignment:
                    isUser ? Alignment.centerRight : Alignment.centerLeft,
                child: Text(
                  timeText,
                  style: AppTypography.mono.copyWith(
                    color: isUser
                        ? context.colors.ink.withValues(alpha: 0.5)
                        : context.colors.inkFaint,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
