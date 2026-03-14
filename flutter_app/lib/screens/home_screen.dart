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
  BulletinGenerationException? _generationError;

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
      _generationError = null;
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
    } on BulletinGenerationException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _generationError = error;
      });
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _generationError = BulletinGenerationException(
          message: 'OpenWave could not generate the next bulletin right now. Please try again.',
        );
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
          if (_generationError != null) ...[
            const SizedBox(height: 16),
            _ErrorNotice(error: _generationError!),
          ],
        ],
      ),
    );
  }
}

class _ErrorNotice extends StatelessWidget {
  const _ErrorNotice({required this.error});

  final BulletinGenerationException error;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final suggestions = error.suggestions;

    return Card(
      color: theme.colorScheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              error.isTtsBudgetIssue ? 'Audio budget limit reached' : 'Generation failed',
              style: theme.textTheme.titleMedium?.copyWith(
                color: theme.colorScheme.onErrorContainer,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              error.userMessage,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onErrorContainer,
              ),
            ),
            if (error.estimateSummary != null) ...[
              const SizedBox(height: 12),
              Text(
                error.estimateSummary!,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onErrorContainer,
                ),
              ),
            ],
            if (error.budgetSummary != null) ...[
              const SizedBox(height: 4),
              Text(
                error.budgetSummary!,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onErrorContainer,
                ),
              ),
            ],
            if (suggestions.isNotEmpty) ...[
              const SizedBox(height: 12),
              for (final suggestion in suggestions)
                Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Text(
                    '- $suggestion',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onErrorContainer,
                    ),
                  ),
                ),
            ],
          ],
        ),
      ),
    );
  }
}
