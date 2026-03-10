import 'package:flutter/material.dart';

import '../models/daily_brief.dart';
import '../services/api_service.dart';
import 'player_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final ApiService _apiService = ApiService();

  DailyBrief? _dailyBrief;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadDailyBrief();
  }

  Future<void> _loadDailyBrief() async {
    try {
      final dailyBrief = await _apiService.getDailyBrief();

      if (!mounted) return;

      setState(() {
        _dailyBrief = dailyBrief;
      });
    } catch (e) {
      debugPrint('Daily brief load error: $e');

      if (!mounted) return;

      setState(() {
        _error = 'Failed to load daily brief.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_error != null) {
      return Scaffold(
        appBar: AppBar(title: const Text('OpenWave')),
        body: Center(child: Text(_error!)),
      );
    }

    if (_dailyBrief == null) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    return PlayerScreen(dailyBrief: _dailyBrief!);
  }
}
