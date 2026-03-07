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
    } catch (_) {
      if (!mounted) return;

      setState(() {
        _error = 'Failed to load daily brief.';
      });
    }
  }

  void _openPlayer() {
    if (_dailyBrief == null) return;

    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => PlayerScreen(dailyBrief: _dailyBrief!),
      ),
    );
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
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                icon: const Icon(Icons.play_arrow),
                label: const Text('Play Daily Brief'),
                onPressed: _openPlayer,
              ),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: ListView.builder(
                itemCount: _dailyBrief!.articles.length,
                itemBuilder: (context, index) {
                  final article = _dailyBrief!.articles[index];

                  return Card(
                    margin: const EdgeInsets.only(bottom: 12),
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            article.title,
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          const SizedBox(height: 4),
                          Text(
                            article.source,
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                          const SizedBox(height: 8),
                          Text(
                            article.summary,
                            maxLines: 3,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
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