import 'package:flutter/material.dart';

import '../../../../theme/app_theme.dart';

/// Input chat (`docs/06-SCREENS.md` S3 → Chat Input & mockup
/// `.chat-input`).
///
/// Pill bgInput + send gold circle 36px.
class ChatInput extends StatefulWidget {
  const ChatInput({
    required this.controller,
    required this.onSend,
    this.enabled = true,
    super.key,
  });

  final TextEditingController controller;
  final ValueChanged<String> onSend;

  /// False saat menunggu balasan bot.
  final bool enabled;

  @override
  State<ChatInput> createState() => _ChatInputState();
}

class _ChatInputState extends State<ChatInput> {
  void _submit() {
    final text = widget.controller.text.trim();
    if (text.isEmpty || !widget.enabled) return;
    widget.onSend(text);
    widget.controller.clear();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.s16,
        AppSpacing.s12,
        AppSpacing.s16,
        AppSpacing.s24,
      ),
      decoration: BoxDecoration(
        color: context.colors.bgApp,
        border: Border(top: BorderSide(color: context.colors.line)),
      ),
      child: Container(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.s16,
          AppSpacing.s6,
          AppSpacing.s6,
          AppSpacing.s6,
        ),
        decoration: BoxDecoration(
          color: context.colors.bgInput,
          borderRadius: BorderRadius.circular(AppRadius.r24),
          border: Border.all(color: context.colors.lineStrong),
        ),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: widget.controller,
                enabled: widget.enabled,
                onSubmitted: (_) => _submit(),
                textInputAction: TextInputAction.send,
                style: AppTypography.bodyM.copyWith(color: context.colors.ink),
                cursorColor: context.colors.gold,
                decoration: InputDecoration(
                  isDense: true,
                  border: InputBorder.none,
                  hintText: 'Tanyakan kondisi kantor...',
                  hintStyle: AppTypography.bodyM.copyWith(
                    color: context.colors.inkFaint,
                  ),
                  contentPadding: const EdgeInsets.symmetric(
                    vertical: AppSpacing.s8,
                  ),
                ),
              ),
            ),
            GestureDetector(
              onTap: _submit,
              child: Container(
                width: 36,
                height: 36,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [context.colors.goldBright, context.colors.gold],
                  ),
                ),
                child: Icon(
                  Icons.send,
                  size: 16,
                  color: context.colors.bgApp,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
