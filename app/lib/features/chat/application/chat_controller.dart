import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api/api_exception.dart';
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

  String? _conversationId;

  /// Kirim pesan user → balasan Codi via `POST /chat/messages`.
  Future<void> send(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || state.isSending) return;

    final userMsg = ChatMessage(
      id: _nextId(),
      sender: MessageSender.user,
      text: trimmed,
      time: DateTime.now(),
    );
    state = state.copyWith(
      messages: [...state.messages, userMsg],
      isSending: true,
      clearError: true,
    );

    try {
      final reply = await ref.read(chatRepositoryProvider).send(
            message: trimmed,
            conversationId: _conversationId,
            screen: 'chat',
          );
      _conversationId = reply.conversationId;
      state = state.copyWith(
        messages: [...state.messages, reply.message],
        suggestions: reply.suggestions.isNotEmpty
            ? reply.suggestions
            : state.suggestions,
        isSending: false,
      );
    } on ApiException catch (e) {
      state = state.copyWith(isSending: false, error: e.message);
    }
  }
}

/// Provider state Chat.
final chatControllerProvider =
    NotifierProvider<ChatController, ChatState>(ChatController.new);
