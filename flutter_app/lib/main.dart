import 'package:flutter/material.dart';

import 'models/user_personalization.dart';
import 'screens/home_screen.dart';
import 'screens/personalization_flow_screen.dart';
import 'services/personalization_storage_service.dart';

void main() {
  runApp(const OpenWaveApp());
}

class OpenWaveApp extends StatefulWidget {
  const OpenWaveApp({super.key});

  @override
  State<OpenWaveApp> createState() => _OpenWaveAppState();
}

class _OpenWaveAppState extends State<OpenWaveApp> {
  final PersonalizationStorageService _storageService =
      PersonalizationStorageService();
  UserPersonalization? _personalization;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadPersonalization();
  }

  Future<void> _loadPersonalization() async {
    final personalization = await _storageService.loadPersonalization();
    if (!mounted) {
      return;
    }
    setState(() {
      _personalization = personalization;
      _isLoading = false;
    });
  }

  void _handlePersonalizationSaved(UserPersonalization personalization) {
    setState(() {
      _personalization = personalization;
      _isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'OpenWave',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF0E5A8A)),
        useMaterial3: true,
      ),
      home: _isLoading
          ? const Scaffold(
              body: Center(child: CircularProgressIndicator()),
            )
          : (_personalization == null
              ? PersonalizationFlowScreen(
                  isOnboarding: true,
                  onSaved: _handlePersonalizationSaved,
                )
              : HomeScreen(
                  personalization: _personalization!,
                  onPersonalizationChanged: _handlePersonalizationSaved,
                )),
    );
  }
}
