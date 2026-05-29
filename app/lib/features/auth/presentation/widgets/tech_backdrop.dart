import 'dart:math' as math;

import 'package:flutter/material.dart';

/// Backdrop animasi tipis bernuansa tech untuk layar Login.
///
/// Jaringan titik (constellation) yang melayang pelan + garis koneksi antar
/// titik terdekat. Opacity rendah supaya halus, di belakang konten. Murni
/// CustomPaint — tanpa dependency, ringan (~24 titik).
class TechBackdrop extends StatefulWidget {
  const TechBackdrop({required this.color, super.key});

  /// Warna dasar titik & garis (alpha diatur internal).
  final Color color;

  @override
  State<TechBackdrop> createState() => _TechBackdropState();
}

class _TechBackdropState extends State<TechBackdrop>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final List<_Node> _nodes;

  @override
  void initState() {
    super.initState();
    // 1 siklus penuh 18 detik — drift sangat pelan.
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 18),
    )..repeat();
    // Posisi deterministik (tanpa Random) — tersebar via index.
    _nodes = List.generate(24, (i) {
      return _Node(
        baseX: ((i * 0.1372) % 1.0),
        baseY: ((i * 0.3791) % 1.0),
        phase: i * 0.41,
        speed: 0.4 + (i % 5) * 0.12,
        radius: 1.2 + (i % 3) * 0.5,
      );
    });
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: RepaintBoundary(
        child: AnimatedBuilder(
          animation: _ctrl,
          builder: (context, _) => CustomPaint(
            size: Size.infinite,
            painter: _NetPainter(
              t: _ctrl.value,
              nodes: _nodes,
              color: widget.color,
            ),
          ),
        ),
      ),
    );
  }
}

class _Node {
  const _Node({
    required this.baseX,
    required this.baseY,
    required this.phase,
    required this.speed,
    required this.radius,
  });
  final double baseX;
  final double baseY;
  final double phase;
  final double speed;
  final double radius;
}

class _NetPainter extends CustomPainter {
  _NetPainter({required this.t, required this.nodes, required this.color});

  final double t;
  final List<_Node> nodes;
  final Color color;

  static const _twoPi = math.pi * 2;
  static const _linkDist = 0.22; // jarak maksimal garis (normalized)

  @override
  void paint(Canvas canvas, Size size) {
    final pts = <Offset>[];
    for (final n in nodes) {
      final dx = n.baseX + 0.035 * math.sin(_twoPi * (t * n.speed + n.phase));
      final dy =
          n.baseY + 0.045 * math.cos(_twoPi * (t * n.speed * 0.8 + n.phase));
      pts.add(Offset((dx % 1.0) * size.width, (dy % 1.0) * size.height));
    }

    final linePaint = Paint()
      ..strokeWidth = 0.7
      ..style = PaintingStyle.stroke;
    final maxPx = _linkDist * size.width;
    for (var i = 0; i < pts.length; i++) {
      for (var j = i + 1; j < pts.length; j++) {
        final d = (pts[i] - pts[j]).distance;
        if (d > maxPx) continue;
        final a = (1.0 - d / maxPx) * 0.10; // garis sangat samar
        linePaint.color = color.withValues(alpha: a);
        canvas.drawLine(pts[i], pts[j], linePaint);
      }
    }

    final dotPaint = Paint()..style = PaintingStyle.fill;
    for (var i = 0; i < pts.length; i++) {
      dotPaint.color = color.withValues(alpha: 0.16);
      canvas.drawCircle(pts[i], nodes[i].radius, dotPaint);
    }
  }

  @override
  bool shouldRepaint(_NetPainter old) => old.t != t || old.color != color;
}
