# Contributing to Brown

Thank you for your interest in contributing to **Brown — Personal AI Computer Assistant**! As an open-source initiative, we welcome developers, researchers, and creators from around the world.

---

## 🛠️ Development Setup

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/<your-username>/hey_brown.git
   cd hey_brown
   ```

2. **Set up a Python 3.11 virtual environment:**
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Verify the test suite passes:**
   ```bash
   PYTHONPATH=. pytest tests/ -v
   ```

---

## 📐 Architecture Guidelines

When adding new capabilities or providers:
1. **Preserve Modularity:** Never tightly couple core logic to a specific vendor. Implement the abstract interfaces in `voice/*/base.py` or `devices/base.py`.
2. **Deterministic Fast-Paths:** Prioritize zero-LLM deterministic paths for repetitive tasks.
3. **Security Boundaries:** Never expose unrestricted shell or OS access to model prompts. All actions must go through typed tools in `tools/`.
4. **Offline Resiliency:** Remote nodes (like Error Boy) must never block local nodes (Paperball) from functioning.

---

## 🚀 Submitting a Pull Request

1. Create a feature branch: `git checkout -b feature/my-new-feature`
2. Write clean, documented code and add tests under `tests/`.
3. Ensure all tests pass: `PYTHONPATH=. pytest tests/ -v`
4. Commit your changes with clear messages.
5. Push to your fork and submit a PR to `main`.
