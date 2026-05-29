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
            state = state.copyWith(isSending: false);
            if (!completer.isCompleted) completer.complete();
          },
          onError: (code, msg) {
            // Replace message bot kosong dengan pesan error.
            if (buffer.isEmpty) appendDelta('⚠️ $msg');
            state = state.copyWith(isSending: false, error: msg);
            if (!completer.isCompleted) completer.complete();
          },
        );
    return completer.future;
  }
}

/// Provider state Chat.
final chatControllerProvider =
    NotifierProvider<ChatController, ChatState>(ChatController.new);
