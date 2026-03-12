import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';

import '../models/tts_pilot.dart';

class PilotTtsPlayerScreen extends StatefulWidget {
  final GeneratedPilotAudio generatedPilotAudio;

  const PilotTtsPlayerScreen({
    super.key,
    required this.generatedPilotAudio,
  });

  @override
  State<PilotTtsPlayerScreen> createState() => _PilotTtsPlayerScreenState();
}

class _PilotTtsPlayerScreenState extends State<PilotTtsPlayerScreen> {
  final AudioPlayer _audioPlayer = AudioPlayer();
  Duration _position = Duration.zero;
  Duration _duration = Duration.zero;
  bool _isPlaying = false;

  @override
  void initState() {
    super.initState();
    _audioPlayer.onPlayerStateChanged.listen((state) {
      if (!mounted) return;
      setState(() {
        _isPlaying = state == PlayerState.playing;
      });
    });
    _audioPlayer.onDurationChanged.listen((duration) {
      if (!mounted) return;
      setState(() {
        _duration = duration;
      });
    });
    _audioPlayer.onPositionChanged.listen((position) {
      if (!mounted) return;
      setState(() {
        _position = position;
      });
    });
    _audioPlayer.onPlayerComplete.listen((_) {
      if (!mounted) return;
      setState(() {
        _isPlaying = false;
        _position = _duration;
      });
    });
  }

  Future<void> _togglePlayback() async {
    if (_isPlaying) {
      await _audioPlayer.pause();
      return;
    }

    if (_position > Duration.zero && _position < _duration) {
      await _audioPlayer.resume();
      return;
    }

    await _audioPlayer.play(UrlSource(widget.generatedPilotAudio.audioUrl));
  }

  Future<void> _restartPlayback() async {
    await _audioPlayer.stop();
    setState(() {
      _position = Duration.zero;
    });
    await _audioPlayer.play(UrlSource(widget.generatedPilotAudio.audioUrl));
  }

  String _formatDuration(Duration duration) {
    final minutes = duration.inMinutes;
    final seconds = duration.inSeconds % 60;
    return '$minutes:${seconds.toString().padLeft(2, '0')}';
  }

  @override
  void dispose() {
    _audioPlayer.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final totalMilliseconds = _duration.inMilliseconds <= 0
        ? 1
        : _duration.inMilliseconds;
    final progress =
        (_position.inMilliseconds / totalMilliseconds).clamp(0.0, 1.0);
    final voiceLabel = widget.generatedPilotAudio.ttsVoiceId.isEmpty
        ? 'default'
        : widget.generatedPilotAudio.ttsVoiceId;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Daily Brief Player'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              widget.generatedPilotAudio.title,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            Text(
              'Presenter: ${widget.generatedPilotAudio.presenterName}',
              style: Theme.of(context).textTheme.bodyLarge,
            ),
            Text(
              'Provider: ${widget.generatedPilotAudio.ttsProvider} | Voice: $voiceLabel',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 16),
            LinearProgressIndicator(value: progress),
            const SizedBox(height: 8),
            Text(
              '${_formatDuration(_position)} / ${_formatDuration(_duration)}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                IconButton(
                  onPressed: _restartPlayback,
                  icon: const Icon(Icons.replay),
                ),
                const SizedBox(width: 12),
                IconButton(
                  onPressed: _togglePlayback,
                  iconSize: 40,
                  icon: Icon(
                    _isPlaying
                        ? Icons.pause_circle_filled
                        : Icons.play_circle_filled,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Text(
              'Transcript',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Expanded(
              child: SingleChildScrollView(
                child: SelectableText(
                  widget.generatedPilotAudio.briefingText,
                  style: Theme.of(context).textTheme.bodyLarge,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
