import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';

import '../models/daily_brief.dart';

class PlayerScreen extends StatefulWidget {
  final DailyBrief dailyBrief;

  const PlayerScreen({
    super.key,
    required this.dailyBrief,
  });

  @override
  State<PlayerScreen> createState() => _PlayerScreenState();
}

class _PlayerScreenState extends State<PlayerScreen> {
  int _currentIndex = 0;
  final FlutterTts _flutterTts = FlutterTts();
  bool _isPlaying = false;
  int _currentProgressSeconds = 0;
  int _currentArticleDurationSeconds = 0;
  Timer? _progressTimer;
  bool _isPlayingCue = false;
  bool _isPlayingIntro = false;

  @override
  void initState() {
    super.initState();
    _flutterTts.setCompletionHandler(() {
      _handleTtsCompletion();
    });
    if (widget.dailyBrief.articles.isNotEmpty) {
      _resetProgressForCurrentArticle();
      WidgetsBinding.instance.addPostFrameCallback((_) async {
        if (!mounted) return;
        setState(() {
          _isPlaying = true;
        });
        await _playIntroIfNeeded();
      });
    }
  }

  Future<void> _playIntroIfNeeded() async {
    final articleCount = widget.dailyBrief.articles.length;
    final countWord = <int, String>{
          1: 'One',
          2: 'Two',
          3: 'Three',
          4: 'Four',
          5: 'Five',
          6: 'Six',
          7: 'Seven',
          8: 'Eight',
          9: 'Nine',
          10: 'Ten',
        }[articleCount] ??
        articleCount.toString();
    final storyLabel = articleCount == 1 ? 'story' : 'stories';

    final totalEstimatedSeconds = widget.dailyBrief.articles
        .map((article) => _estimateDurationSeconds(_buildNarrationText(article)))
        .fold(0, (sum, duration) => sum + duration);
    final roundedMinutes = (totalEstimatedSeconds / 60).round();
    final safeMinutes = roundedMinutes < 1 ? 1 : roundedMinutes;
    final minuteWord = <int, String>{
          1: 'one',
          2: 'two',
          3: 'three',
          4: 'four',
          5: 'five',
          6: 'six',
          7: 'seven',
          8: 'eight',
          9: 'nine',
          10: 'ten',
        }[safeMinutes] ??
        safeMinutes.toString();
    final minuteLabel = safeMinutes == 1 ? 'minute' : 'minutes';

    _isPlayingIntro = true;
    await _flutterTts.speak(
      'Your OpenWave Daily Brief. $countWord $storyLabel today. About $minuteWord $minuteLabel.',
    );
  }

  Future<void> _handleTtsCompletion() async {
    if (!_isPlaying) return;

    if (_isPlayingIntro) {
      _isPlayingIntro = false;
      _isPlayingCue = true;
      await _flutterTts.speak('Top story.');
      return;
    }

    if (_isPlayingCue) {
      _isPlayingCue = false;
      if (_currentIndex == 0) {
        await _playCurrentArticle();
        return;
      }
      setState(() {
        _currentIndex++;
      });
      await _playCurrentArticle();
      return;
    }

    final hasNext = _currentIndex < widget.dailyBrief.articles.length - 1;
    if (hasNext) {
      _stopProgressTimer();
      _isPlayingCue = true;
      await _flutterTts.speak('Next story.');
      return;
    }

    _stopProgressTimer();
    _isPlayingCue = false;
    await _flutterTts.stop();
    if (!mounted) return;
    setState(() {
      _isPlaying = false;
      _currentProgressSeconds = _currentArticleDurationSeconds;
    });
  }

  String _buildNarrationText(DailyBriefArticle article) {
    return '${article.title}. ${article.summary}';
  }

  int _estimateDurationSeconds(String text) {
    final words = text
        .trim()
        .split(RegExp(r'\s+'))
        .where((word) => word.isNotEmpty)
        .length;
    if (words == 0) return 0;

    return ((words / 170) * 60).ceil();
  }

  String _formatDuration(int seconds) {
    final safeSeconds = seconds < 0 ? 0 : seconds;
    final minutes = safeSeconds ~/ 60;
    final remainingSeconds = safeSeconds % 60;
    final paddedSeconds = remainingSeconds.toString().padLeft(2, '0');

    return '$minutes:$paddedSeconds';
  }

  void _resetProgressForCurrentArticle() {
    final articles = widget.dailyBrief.articles;
    if (articles.isEmpty) {
      _currentProgressSeconds = 0;
      _currentArticleDurationSeconds = 0;
      return;
    }

    final text = _buildNarrationText(articles[_currentIndex]);
    _currentProgressSeconds = 0;
    _currentArticleDurationSeconds = _estimateDurationSeconds(text);
  }

  void _startProgressTimer() {
    _stopProgressTimer();
    if (_currentArticleDurationSeconds <= 0) return;

    _progressTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }

      setState(() {
        if (_currentProgressSeconds < _currentArticleDurationSeconds) {
          _currentProgressSeconds++;
        } else {
          timer.cancel();
        }
      });
    });
  }

  void _stopProgressTimer() {
    _progressTimer?.cancel();
    _progressTimer = null;
  }

  Future<void> _selectArticle(int index) async {
    setState(() {
      _currentIndex = index;
      _resetProgressForCurrentArticle();
    });

    if (_isPlaying) {
      await _flutterTts.stop();
      await _playCurrentArticle();
    }
  }

  Future<void> _playPrevious() async {
    if (_currentIndex == 0) return;

    setState(() {
      _currentIndex--;
      _resetProgressForCurrentArticle();
    });

    if (_isPlaying) {
      await _flutterTts.stop();
      await _playCurrentArticle();
    }
  }

  Future<void> _playNext() async {
    if (_currentIndex >= widget.dailyBrief.articles.length - 1) return;

    setState(() {
      _currentIndex++;
      _resetProgressForCurrentArticle();
    });

    if (_isPlaying) {
      await _flutterTts.stop();
      await _playCurrentArticle();
    }
  }

  Future<void> _playCurrentArticle() async {
    final articles = widget.dailyBrief.articles;
    if (articles.isEmpty) return;

    final article = articles[_currentIndex];
    final text = _buildNarrationText(article);

    if (text.trim().isEmpty) return;

    setState(() {
      _currentProgressSeconds = 0;
      _currentArticleDurationSeconds = _estimateDurationSeconds(text);
    });
    _startProgressTimer();

    await _flutterTts.speak(text);
  }

  Future<void> _togglePlayback() async {
    if (_isPlaying) {
      _isPlayingCue = false;
      _isPlayingIntro = false;
      _stopProgressTimer();
      await _flutterTts.stop();
      setState(() {
        _isPlaying = false;
      });
      return;
    }

    setState(() {
      _isPlaying = true;
    });
    await _playCurrentArticle();
  }

  @override
  void dispose() {
    _stopProgressTimer();
    _flutterTts.stop();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final articles = widget.dailyBrief.articles;
    final nowPlaying = articles.isNotEmpty ? articles[_currentIndex] : null;
    final narrationText =
        nowPlaying != null ? _buildNarrationText(nowPlaying) : '';
    final nextArticle = _currentIndex < articles.length - 1
        ? articles[_currentIndex + 1]
        : null;
    final estimatedDurationLabel = _currentArticleDurationSeconds >= 60
        ? '${(_currentArticleDurationSeconds / 60).round()} min'
        : '$_currentArticleDurationSeconds sec';
    final progressValue = _currentArticleDurationSeconds > 0
        ? (_currentProgressSeconds / _currentArticleDurationSeconds)
            .clamp(0.0, 1.0)
            .toDouble()
        : 0.0;
    final remainingSeconds =
        (_currentArticleDurationSeconds - _currentProgressSeconds)
            .clamp(0, _currentArticleDurationSeconds);

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
              widget.dailyBrief.headline,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            Text(
              '${articles.length} stories',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 24),
            if (nowPlaying != null) ...[
              Text(
                'Now Playing',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 8),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        nowPlaying.title,
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        nowPlaying.source,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        nowPlaying.summary,
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                      if (narrationText.isNotEmpty) ...[
                        const SizedBox(height: 8),
                        Text(
                          'Audio narration ready',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                      const SizedBox(height: 8),
                      Text(
                        estimatedDurationLabel,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 16),
                      LinearProgressIndicator(
                        value: progressValue,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '${_formatDuration(_currentProgressSeconds)} / ${_formatDuration(_currentArticleDurationSeconds)}  •  -${_formatDuration(remainingSeconds)}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 12),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          IconButton(
                            onPressed: _playPrevious,
                            icon: const Icon(Icons.skip_previous),
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
                          const SizedBox(width: 12),
                          IconButton(
                            onPressed: _playNext,
                            icon: const Icon(Icons.skip_next),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              if (nextArticle != null) ...[
                const SizedBox(height: 12),
                Text(
                  'Up next: ${nextArticle.title}',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ],
              const SizedBox(height: 24),
            ],
            Text(
              'Playlist',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Expanded(
              child: ListView.builder(
                itemCount: articles.length,
                itemBuilder: (context, index) {
                  final article = articles[index];
                  final isActive = index == _currentIndex;
                  final playlistNarrationText = _buildNarrationText(article);
                  final playlistDurationSeconds =
                      _estimateDurationSeconds(playlistNarrationText);
                  final playlistDurationLabel = playlistDurationSeconds >= 60
                      ? '${(playlistDurationSeconds / 60).round()} min'
                      : '$playlistDurationSeconds sec';

                  return Card(
                    color: isActive
                        ? Theme.of(context).colorScheme.primaryContainer
                        : null,
                    shape: RoundedRectangleBorder(
                      side: BorderSide(
                        color: isActive
                            ? Theme.of(context).colorScheme.primary
                            : Colors.transparent,
                        width: isActive ? 2 : 0,
                      ),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: ListTile(
                      onTap: () => _selectArticle(index),
                      leading: CircleAvatar(
                        child: Text('${index + 1}'),
                      ),
                      title: Text(
                        article.title,
                        style: isActive
                            ? Theme.of(context).textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.w600,
                              )
                            : null,
                      ),
                      subtitle: isActive
                          ? Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text('${article.source} • $playlistDurationLabel'),
                                Text(
                                  'Playing now',
                                  style: Theme.of(context)
                                      .textTheme
                                      .bodySmall
                                      ?.copyWith(
                                        fontWeight: FontWeight.w600,
                                      ),
                                ),
                              ],
                            )
                          : Text('${article.source} • $playlistDurationLabel'),
                      trailing: Icon(
                        isActive ? Icons.graphic_eq : Icons.play_arrow,
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
