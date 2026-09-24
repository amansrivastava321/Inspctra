import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

void main() {
  runApp(const SampleApp());
}

class SampleApp extends StatelessWidget {
  const SampleApp({super.key});

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(home: Scaffold(body: Center(child: SyncScreen())));
  }
}

class SyncScreen extends StatefulWidget {
  const SyncScreen({super.key});

  @override
  State<SyncScreen> createState() => _SyncScreenState();
}

class _SyncScreenState extends State<SyncScreen> {
  String status = "idle";

  Future<void> sendSync() async {
    setState(() => status = "syncing");
    try {
      // Missing auth token and weak retry semantics by design.
      await http.post(Uri.parse("https://example.com/sync"));
      await http.post(Uri.parse("https://example.com/sync"));
      setState(() => status = "done");
    } catch (_) {
      // Weak error handling.
      setState(() => status = "error");
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        ElevatedButton(
          onPressed: sendSync,
          // UI inconsistency: odd shape/styling compared to standard controls.
          style: ElevatedButton.styleFrom(shape: const StadiumBorder()),
          child: const Text("Sync Now"),
        ),
        Text(status),
        const Text("TODO: offline queue conflict resolver"),
        const Text("FIXME: prevent duplicate submission"),
      ],
    );
  }
}
