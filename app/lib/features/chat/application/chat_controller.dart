import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api/repositories/chat_repository.dart';
import '../../../models/chat_message.dart';
import '../domain/chat_state.dart';

/// Controller Chat.
///
/// Backend `POST /chat/messages` real — `backend/core/mobile_api.py`
/// wire ke orchestrator Claude CLI (role advisor). History dimulai
/// dengan welcome message; user/bot turn ditambah saat kirim.
class ChatController extends Notifier<ChatState> {
  int _seq = 0;

  @override
  ChatState build() {
    return const ChatState(
      messages: [],
      suggestions: [
        '📊 Ringkasan kondisi hari ini',
        '📈 Proyeksi akhir bulan',
        '👥 Status karyawan',
      ],
    );
  }

  String _nextId() => 'm${_seq++}';

  /// Kirim pesan user → balasan Codi via SSE streaming
  /// (`POST /chat/messages/stream`). Reply bot di-append token-by-token
  /// agar UI terlihat hidup.
  Future<void> send(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || state.isSending) return;

    final userMsg = ChatMessage(
      id: _nextId(),
      sender: MessageSender.user,
      text: trimmed,
      time: DateTime.now(),
    );
    // Bot bubble placeholder yang diisi incrementally.
    final botId = _nextId();
    final botMsg = ChatMessage(
      id: botId,
      sender: MessageSender.bot,
      text: '',
      time: DateTime.now(),
    );
    state = state.copyWith(
      messages: [...state.messages, userMsg, botMsg],
      isSending: true,
      clearError: true,
    );

    final buffer = StringBuffer();
    void appendDelta(String delta) {
      buffer.write(delta);
      // Update message bot terakhir dengan buffer terbaru.
      final msgs = [...state.messages];
      final idx = msgs.indexWhere((m) => m.id == botId);
      if (idx < 0) return;
      msgs[idx] = ChatMessage(
        id: botMsg.id,
        sender: MessageSender.bot,
        text: buffer.toString(),
        time: botMsg.time,
      );
      state = state.copyWith(messages: msgs);
    }

    final completer = Completer<void>();
    await ref.read(chatRepositoryProvider).sendStream(
          message: trimmed,
          onToken: appendDelta,
          onDone: () {
            if (buffer.isEmpty) {
              appendDelta(
                'Maaf, jawaban kosong dari server. Silakan coba lagi.',
              );
            }
            // Final cleanup: strip markdown yang lolos (** _ # ```).
            // Selama streaming kita biarkan literal supaya user lihat reply
            // hidup; di akhir kita rapikan untuk presentasi profesional.
            final cleaned = _cleanMarkdown(buffer.toString());
            final msgs = [...state.messages];
            final idx = msgs.indexWhere((m) => m.id == botId);
            if (idx >= 0) {
              msgs[idx] = ChatMessage(
                id: botMsg.id,
                sender: MessageSender.bot,
                text: cleaned,
                time: botMsg.time,
              );
            }
            state = state.copyWith(messages: msgs, isSending: false);
            if (!completer.isCompleted) completer.complete();
          },
          onError: (code, msg) {
            if (buffer.isEmpty) appendDelta('⚠️ $msg');
            state = state.copyWith(isSending: false, error: msg);
            if (!completer.isCompleted) completer.complete();
          },
        );
    return completer.future;
  }

  /// Strip markdown inline (`**bold**`, `*italic*`, `__b__`, `_i_`,
  /// `` `code` ``, `~~strike~~`, fence `````` ` `````` , heading `#`,
  /// link `[label](url)`) → plain text. Backend Codi sering balas dgn
  /// markdown; mobile bubble render `Text` plain jadi tag bocor literal.
  static String _cleanMarkdown(String raw) {
    if (raw.isEmpty) return raw;
    var s = raw;
    // Code fence ```lang\n...```.
    s = s.replaceAllMapped(
      RegExp(r'```[a-zA-Z0-9_+-]*\n?([\s\S]*?)```', multiLine: true),
      (m) => m.group(1) ?? '',
    );
    // Link [label](href) → label.
    s = s.replaceAllMapped(
      RegExp(r'\[([^\]]+)\]\([^)]+\)'),
      (m) => m.group(1) ?? '',
    );
    // **bold** / __bold__.
    s = s.replaceAllMapped(
      RegExp(r'\*\*([^*\n]+?)\*\*'),
      (m) => m.group(1) ?? '',
    );
    s = s.replaceAllMapped(
      RegExp(r'__([^_\n]+?)__'),
      (m) => m.group(1) ?? '',
    );
    // *italic* / _italic_ (no word-boundary mismatch).
    s = s.replaceAllMapped(
      RegExp(r'(?<![*\w])\*([^*\n]+?)\*(?!\w)'),
      (m) => m.group(1) ?? '',
    );
    s = s.replaceAllMapped(
      RegExp(r'(?<![_\w])_([^_\n]+?)_(?!\w)'),
      (m) => m.group(1) ?? '',
    );
    // `inline code`.
    s = s.replaceAllMapped(
      RegExp(r'`([^`\n]+?)`'),
      (m) => m.group(1) ?? '',
    );
    // ~~strike~~.
    s = s.replaceAllMapped(
      RegExp(r'~~([^~\n]+?)~~'),
      (m) => m.group(1) ?? '',
    );
    // Heading marker `## ` → ''.
    s = s.replaceAll(RegExp(r'^\s{0,3}#{1,6}\s+', multiLine: true), '');
    // Collapse 3+ newlines → 2.
    s = s.replaceAll(RegExp(r'\n{3,}'), '\n\n');
    // Strip trailing whitespace per line.
    s = s.split('\n').map((l) => l.trimRight()).join('\n');
    return s.trim();
  }
}

/// Provider state Chat.
final chatControllerProvider =
    NotifierProvider<ChatController, ChatState>(ChatController.new);
