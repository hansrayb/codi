import 'package:flutter/foundation.dart';

import '../../../models/chat_message.dart';

/// State Chat (`docs/06-SCREENS.md` S3 → State).
@immutable
class ChatState {
  const ChatState({
    this.messages = const [],
    this.suggestions = const [],
    this.isSending = false,
    this.error,
  });

  final List<ChatMessage> messages;
  final List<String> suggestions;

  /// True saat menunggu balasan bot.
  final bool isSending;

  final String? error;

  ChatState copyWith({
    List<ChatMessage>? messages,
    List<String>? suggestions,
    bool? isSending,
    String? error,
    bool clearError = false,
  }) {
    return ChatState(
      messages: messages ?? this.messages,
      suggestions: suggestions ?? this.suggestions,
      isSending: isSending ?? this.isSending,
      error: clearError ? null : (error ?? this.error),
    );
  }
}
