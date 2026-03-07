import 'package:flutter/material.dart';

import '../models/daily_brief.dart';
import '../services/api_service.dart';

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
    } catch (_) {
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

    return Scaffold(
      appBar: AppBar(title: const Text('OpenWave')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              _dailyBrief!.headline,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 16),
            Expanded(
              child: ListView.builder(
                itemCount: _dailyBrief!.highlights.length,
                itemBuilder: (context, index) {
                  return ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(_dailyBrief!.highlights[index]),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
