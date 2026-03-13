import 'package:flutter/material.dart';

import '../models/daily_brief.dart';
import '../models/user_personalization.dart';
import '../services/api_service.dart';
import 'personalization_flow_screen.dart';
import 'player_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({
    super.key,
    required this.personalization,
    required this.onPersonalizationChanged,
  });

  final UserPersonalization personalization;
  final ValueChanged<UserPersonalization> onPersonalizationChanged;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final ApiService _apiService = ApiService();
  bool _isGenerating = false;
  String? _error;

  Future<void> _openPersonalizationSettings() async {
    final updated = await Navigator.of(context).push<UserPersonalization>(
      MaterialPageRoute<UserPersonalization>(
        builder: (_) => PersonalizationFlowScreen(
          isOnboarding: false,
          initialPersonalization: widget.personalization,
        ),
      ),
    );

    if (updated == null || !mounted) {
      return;
    }

    widget.onPersonalizationChanged(updated);
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Personalization updated. It will apply to the next bulletin.'),
      ),
    );
  }

  Future<void> _generateBulletin() async {
    setState(() {
      _isGenerating = true;
      _error = null;
    });

    try {
      final dailyBrief = await _apiService.generatePersonalizedBulletin(
        widget.personalization,
      );

      if (!mounted) {
        return;
      }

      await Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => PlayerScreen(
            dailyBrief: dailyBrief,
            personalization: widget.personalization,
            onPersonalizationChanged: widget.onPersonalizationChanged,
          ),
        ),
      );
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = error.toString();
      });
    } finally {
      if (!mounted) {
        return;
      }
      setState(() {
        _isGenerating = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final personalization = widget.personalization;
    final geography = personalization.editorialPreferences.geography;
    final domains = personalization.editorialPreferences.domains.rankedEntries();

    return Scaffold(
      appBar: AppBar(
        title: const Text('OpenWave'),
        actions: [
          IconButton(
            onPressed: _openPersonalizationSettings,
            icon: const Icon(Icons.settings),
            tooltip: 'Personalization settings',
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            'Your personalized briefing',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 8),
          Text(
            'OpenWave will reuse your profile and editorial mix for the next generated bulletin.',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 20),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    personalization.listenerProfile.firstName,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 8),
                  Text(personalization.locationSummary),
                  const SizedBox(height: 12),
                  Text(
                    'Geography: local ${geography.local} / national ${geography.national} / international ${geography.international}',
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Top domains: ${domains.take(3).map((entry) => '${entry.key} ${entry.value}').join(' | ')}',
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: _isGenerating ? null : _generateBulletin,
            icon: _isGenerating
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.play_circle_fill),
            label: Text(_isGenerating
                ? 'Generating briefing...'
                : 'Generate next bulletin'),
          ),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: _openPersonalizationSettings,
            icon: const Icon(Icons.tune),
            label: const Text('Edit personalization'),
          ),
          if (_error != null) ...[
            const SizedBox(height: 16),
            Text(
              _error!,
              style: TextStyle(
                color: Theme.of(context).colorScheme.error,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
