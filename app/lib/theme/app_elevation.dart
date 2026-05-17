import 'package:flutter/widgets.dart';

/// Shadow token Emas Berlian Insight.
///
/// Sumber kebenaran: `docs/03-DESIGN-SYSTEM.md`. CSS `0 Yoff Yblur color`
/// dipetakan ke [BoxShadow] (`offset`, `blurRadius`, `spread`).
abstract final class AppElevation {
  const AppElevation._();

  /// Flat — tanpa shadow.
  static const List<BoxShadow> elev0 = <BoxShadow>[];

  /// Card subtle — `0 4px 12px rgba(0,0,0,0.3)`.
  static const List<BoxShadow> elev1 = <BoxShadow>[
    BoxShadow(
      color: Color(0x4D000000),
      offset: Offset(0, 4),
      blurRadius: 12,
    ),
  ];

  /// FAB Codi — `0 10px 24px -4px rgba(201,168,87,0.4)`.
  static const List<BoxShadow> elev2 = <BoxShadow>[
    BoxShadow(
      color: Color(0x66C9A857),
      offset: Offset(0, 10),
      blurRadius: 24,
      spreadRadius: -4,
    ),
  ];

  /// Logo, hero card — `0 20px 50px rgba(74,123,200,0.2)`.
  static const List<BoxShadow> elev3 = <BoxShadow>[
    BoxShadow(
      color: Color(0x334A7BC8),
      offset: Offset(0, 20),
      blurRadius: 50,
    ),
  ];
}
