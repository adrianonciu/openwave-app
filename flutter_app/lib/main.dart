import 'package:flutter/material.dart';

import 'screens/home_screen.dart';

void main() {
  runApp(const OpenWaveApp());
}

class OpenWaveApp extends StatelessWidget {
  const OpenWaveApp({super.key});

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(
      home: HomeScreen(),
    );
  }
}
