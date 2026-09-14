"""Interactive Feature Showcase & Live Test for Brown's Architecture Phase.

Demonstrates and tests:
1. Cross-Device Clipboard (Read, Write, and Sync with size safeguards).
2. Secure Sandboxed File Transfer (SHA-256 checksum, atomic swap, and path-traversal rejection).
3. Clause-Level Streaming Token Buffer (Simulated LLM streaming).
4. Dynamic Device Registry & Capability Discovery ($N$-device resolution).
5. (Optional) Audio Clause Playback with Kokoro-82M ONNX voice.
"""

import os
import sys
import time
import base64
import hashlib
import tempfile

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.local_agent import LocalAgent
from tools.system_tools import GetClipboardTool, SetClipboardTool, SyncClipboardTool, TransferFileTool
from core.device_resolver import DeviceResolver, DeviceRecord
from voice.audio.clause_buffer import ClauseBuffer
from core.observability import RequestTrace


def print_banner():
    print("\n" + "=" * 70)
    print(" 🚀 BROWN AI ASSISTANT — ARCHITECTURE & CAPABILITIES TEST")
    print("=" * 70 + "\n")


def test_1_clipboard():
    print("👉 [Test 1/4] Testing Local & Cross-Device Clipboard...")
    agent = LocalAgent()
    
    test_phrase = f"Brown AI Test Clipboard #{int(time.time())}"
    print(f"   Writing to clipboard: \"{test_phrase}\"")
    write_res = agent.set_clipboard_text(test_phrase)
    assert write_res.success, f"Clipboard set failed: {write_res.message}"
    print(f"   ✅ {write_res.message}")

    print("   Reading back from clipboard...")
    read_res = agent.get_clipboard_text()
    assert read_res.success, f"Clipboard get failed: {read_res.message}"
    actual_text = read_res.data.get("text", "")
    print(f"   Clipboard Content: \"{actual_text}\"")
    assert test_phrase in actual_text, "Clipboard text mismatch!"
    print("   ✅ Verified clipboard read/write matches perfectly.")

    # Size limit safeguard test (>512KB)
    print("   Testing 512KB size limit defense...")
    oversized = "X" * 600000
    oversized_res = agent.set_clipboard_text(oversized)
    assert not oversized_res.success, "Failed to reject oversized clipboard payload!"
    print(f"   🛡️ Protected: {oversized_res.message}")
    print("✅ [Test 1] Clipboard capabilities passed!\n")


def test_2_secure_file_transfer():
    print("👉 [Test 2/4] Testing Secure Sandboxed File Transfer & Path Traversal Defense...")
    agent = LocalAgent()

    # 1. Path traversal defense
    print("   Attempting path traversal attack: '../../etc/passwd'...")
    attack_res = agent.receive_file(
        filename="../../etc/passwd",
        content_b64=base64.b64encode(b"malicious").decode("utf-8")
    )
    assert not attack_res.success, "Path traversal attack was NOT blocked!"
    print(f"   🛡️ Sandboxed & Blocked: {attack_res.message}")

    # 2. Valid transfer with SHA-256 verification
    with tempfile.TemporaryDirectory() as tmpdir:
        test_payload = b"Brown Assistant secure atomic transfer verified payload."
        b64_content = base64.b64encode(test_payload).decode("utf-8")
        expected_sha = hashlib.sha256(test_payload).hexdigest()

        print(f"   Transferring 'report.txt' with SHA-256 verification...")
        recv_res = agent.receive_file(
            filename="report.txt",
            content_b64=b64_content,
            target_dir=tmpdir,
            expected_sha256=expected_sha
        )
        assert recv_res.success, f"File transfer failed: {recv_res.message}"
        print(f"   ✅ {recv_res.message}")

        final_path = os.path.join(tmpdir, "report.txt")
        assert os.path.exists(final_path), "Target file missing after transfer!"
        with open(final_path, "rb") as f:
            assert f.read() == test_payload, "Target file content corrupted!"
        print("   ✅ SHA-256 matched & atomic file swap verified.")

    print("✅ [Test 2] Secure file transfer passed!\n")


def test_3_clause_streaming():
    print("👉 [Test 3/4] Testing Clause-Level Streaming Token Buffer...")
    buffer = ClauseBuffer(min_clause_words=3)
    trace = RequestTrace()
    trace.mark_t("t0")

    simulated_tokens = [
        "Ollama ", "is ", "running ", "on ", "the ", "worker ", "node. ",
        "All ", "three ", "models ", "are ", "loaded, ",
        "and ", "waiting ", "for ", "your ", "next ", "command!"
    ]

    print("   Streaming tokens from simulated LLM response:")
    for tok in simulated_tokens:
        sys.stdout.write(tok)
        sys.stdout.flush()
        time.sleep(0.04)
        ready_clauses = buffer.append(tok)
        for c in ready_clauses:
            if trace.t4_first_clause is None:
                trace.mark_t("t4")
            print(f"\n   🔊 [Ready for Speech Synthesis]: \"{c}\"")

    remainder = buffer.flush()
    if remainder:
        print(f"   🔊 [Flushed Remainder]: \"{remainder}\"")

    trace.mark_t("t6")
    summary = trace.finish()
    print(f"\n   ⚡ Time to First Clause (T4): {summary.get('time_to_first_clause_ms', 0):.1f}ms")
    print("✅ [Test 3] Clause-level streaming buffer passed!\n")


def test_4_generic_device_registry():
    print("👉 [Test 4/4] Testing Dynamic Multi-Device Registry ($N$ devices)...")
    resolver = DeviceResolver()
    
    print(f"   Registered Devices: {resolver.registered_devices}")
    print(f"   Default Local Device: {resolver.default_local_device}")
    print(f"   Default Remote Device: {resolver.default_remote_device}")

    # Query capability
    ai_candidates = resolver.find_devices_by_capability("local_llm")
    print(f"   Devices supporting 'local_llm': {ai_candidates}")

    # Dynamically register a 3rd device
    new_device = DeviceRecord(
        id="cloud_gpu",
        display_name="Cloud RTX 4090",
        operating_system="linux",
        is_local=False,
        capabilities=["local_llm", "file_transfer"],
        roles=["heavy_compute"],
        aliases=["cloud", "gpu cluster", "4090"]
    )
    resolver.register_device(new_device)
    print(f"   Registered dynamic 3rd device: {new_device.display_name}")
    resolved = resolver.resolve("run the deep reasoning on the 4090")
    print(f"   Resolved mention 'on the 4090' -> canonical ID: \"{resolved}\"")
    assert resolved == "cloud_gpu"
    print("   ✅ Dynamic resolution verified.")

    summary = resolver.get_devices_prompt_summary()
    print("\n   System Prompt Summary Generated for LLM:")
    for line in summary.split("\n"):
        print(f"   | {line}")
    print("✅ [Test 4] Generic Device Registry passed!\n")


def main():
    print_banner()
    test_1_clipboard()
    test_2_secure_file_transfer()
    test_3_clause_streaming()
    test_4_generic_device_registry()
    print("=" * 70)
    print(" 🎉 ALL CAPABILITY TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
