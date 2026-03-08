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

  @override
  void initState() {
    super.initState();
    _flutterTts.setCompletionHandler(() {
      _handleTtsCompletion();
    });
  }

  Future<void> _handleTtsCompletion() async {
    if (!_isPlaying) return;

    final hasNext = _currentIndex < widget.dailyBrief.articles.length - 1;
    if (hasNext) {
      setState(() {
        _currentIndex++;
      });
      await _playCurrentArticle();
      return;
    }

    await _flutterTts.stop();
    if (!mounted) return;
    setState(() {
      _isPlaying = false;
    });
  }

  String _buildNarrationText(DailyBriefArticle article) {
    return '${article.title}. ${article.summary}';
  }

  void _selectArticle(int index) {
    setState(() {
      _currentIndex = index;
    });
  }

  void _playPrevious() {
    if (_currentIndex == 0) return;

    setState(() {
      _currentIndex--;
    });
  }

  void _playNext() {
    if (_currentIndex >= widget.dailyBrief.articles.length - 1) return;

    setState(() {
      _currentIndex++;
    });
  }

  Future<void> _playCurrentArticle() async {
    final articles = widget.dailyBrief.articles;
    if (articles.isEmpty) return;

    final article = articles[_currentIndex];
    final text = _buildNarrationText(article);

    if (text.trim().isEmpty) return;
    await _flutterTts.speak(text);
  }

  Future<void> _togglePlayback() async {
    if (_isPlaying) {
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
                        '30 sec',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 16),
                      LinearProgressIndicator(
                        value: (_currentIndex + 1) / articles.length,
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

                  return Card(
                    color: isActive
                        ? Theme.of(context).colorScheme.primaryContainer
                        : null,
                    child: ListTile(
                      onTap: () => _selectArticle(index),
                      leading: CircleAvatar(
                        child: Text('${index + 1}'),
                      ),
                      title: Text(article.title),
                      subtitle: Text(article.source),
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
