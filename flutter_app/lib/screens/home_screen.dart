import 'package:flutter/material.dart';

import '../models/tts_pilot.dart';
import '../services/api_service.dart';
import 'pilot_tts_player_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final ApiService _apiService = ApiService();

  List<TtsPilotSummary> _pilots = const [];
  String? _error;
  String? _loadingPilotId;

  @override
  void initState() {
    super.initState();
    _loadPilots();
  }

  Future<void> _loadPilots() async {
    try {
      final pilots = await _apiService.getTtsPilots();

      if (!mounted) return;

      setState(() {
        _pilots = pilots;
        _error = null;
      });
    } catch (e) {
      debugPrint('TTS pilot load error: $e');

      if (!mounted) return;

      setState(() {
        _error = 'Failed to load Corina TTS pilots.';
      });
    }
  }

  Future<void> _openPilot(TtsPilotSummary pilot) async {
    setState(() {
      _loadingPilotId = pilot.pilotId;
    });

    try {
      final generatedAudio = await _apiService.generatePilotAudio(pilot.pilotId);

      if (!mounted) return;

      await Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) =>
              PilotTtsPlayerScreen(generatedPilotAudio: generatedAudio),
        ),
      );
    } catch (e) {
      debugPrint('Pilot audio generation error: $e');

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Failed to generate pilot audio.'),
        ),
      );
    } finally {
      if (!mounted) return;
      setState(() {
        _loadingPilotId = null;
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

    if (_pilots.isEmpty) {
      return const Scaffold(
        appBar: AppBar(title: Text('OpenWave')),
        body: Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('OpenWave')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            'Corina TTS testing pilots',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 8),
          Text(
            'Generate backend audio for the editorial pilots and play it in the OpenWave player.',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 16),
          for (final pilot in _pilots)
            Card(
              child: ListTile(
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 8,
                ),
                title: Text(pilot.title),
                subtitle: Text('Presenter: ${pilot.presenterName}'),
                trailing: _loadingPilotId == pilot.pilotId
                    ? const SizedBox(
                        width: 24,
                        height: 24,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.play_circle_fill),
                onTap: _loadingPilotId == null ? () => _openPilot(pilot) : null,
              ),
            ),
        ],
      ),
    );
  }
}
