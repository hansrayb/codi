import 'package:flutter/material.dart';
import 'package:speech_to_text/speech_to_text.dart';

import '../../../../theme/app_theme.dart';

/// Input chat (`docs/06-SCREENS.md` S3 → Chat Input & mockup
/// `.chat-input`).
///
/// Pill bgInput, mic ghost (non-aktif Phase 1), send gold circle 36px.
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
  final SpeechToText _speech = SpeechToText();
  bool _speechReady = false;
  bool _listening = false;

  @override
  void dispose() {
    _speech.cancel();
    super.dispose();
  }

  void _submit() {
    final text = widget.controller.text.trim();
    if (text.isEmpty || !widget.enabled) return;
    widget.onSend(text);
    widget.controller.clear();
  }

  void _snack(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(msg)));
  }

  /// Toggle voice input (speech-to-text id_ID). Hasil transkrip masuk ke
  /// controller; user bisa edit / kirim manual.
  Future<void> _toggleMic() async {
    if (!widget.enabled) return;
    if (_listening) {
      await _speech.stop();
      if (mounted) setState(() => _listening = false);
      return;
    }
    if (!_speechReady) {
      _speechReady = await _speech.initialize(
        onStatus: (s) {
          if ((s == 'done' || s == 'notListening') && mounted) {
            setState(() => _listening = false);
          }
        },
        onError: (_) {
          if (mounted) setState(() => _listening = false);
        },
      );
    }
    if (!_speechReady) {
      _snack('Mikrofon atau izin suara tidak tersedia.');
      return;
    }
    setState(() => _listening = true);
    await _speech.listen(
      onResult: (r) {
        widget.controller.text = r.recognizedWords;
        widget.controller.selection = TextSelection.collapsed(
          offset: widget.controller.text.length,
        );
      },
      listenOptions: SpeechListenOptions(
        partialResults: true,
        cancelOnError: true,
        localeId: 'id_ID',
      ),
    );
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
            // Mic — voice input (speech-to-text). Merah saat mendengarkan.
            GestureDetector(
              onTap: _toggleMic,
              behavior: HitTestBehavior.opaque,
              child: Container(
                width: 36,
                height: 36,
                alignment: Alignment.center,
                decoration: _listening
                    ? BoxDecoration(
                        shape: BoxShape.circle,
                        color: context.colors.red.withValues(alpha: 0.15),
                      )
                    : null,
                child: Icon(
                  _listening ? Icons.mic : Icons.mic_none,
                  size: 18,
                  color: _listening
                      ? context.colors.red
                      : context.colors.inkDim,
                ),
              ),
            ),
            const SizedBox(width: AppSpacing.s4),
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
