import re
import sys
import threading
import queue
import traceback
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Coder Buddy",
    page_icon="🤖",
    layout="wide",
)

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🤖 Coder Buddy")
    st.caption("AI-powered project generator")
    st.divider()
    st.header("Settings")
    recursion_limit = st.slider("Recursion limit", 10, 300, 100, step=10)
    st.divider()
    st.markdown("**Generated files** appear in `./generated_project/`")
    if st.button("Open output folder"):
        import subprocess
        folder = Path.cwd() / "generated_project"
        folder.mkdir(exist_ok=True)
        subprocess.Popen(f'explorer "{folder}"')

# ── session state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "running" not in st.session_state:
    st.session_state.running = False
if "result" not in st.session_state:
    st.session_state.result = None

# ── helpers ───────────────────────────────────────────────────────────────────

def list_generated_files() -> list[str]:
    root = Path.cwd() / "generated_project"
    if not root.exists():
        return []
    return sorted(str(f.relative_to(root)) for f in root.rglob("*") if f.is_file())


PREVIEW_EXTENSIONS = {".html", ".htm"}
REACT_INDICATORS = {"jsx", "tsx", "react", "vite", "next"}


def is_react_project(files: list[str]) -> bool:
    text = " ".join(files).lower()
    return any(ind in text for ind in REACT_INDICATORS)


def inline_assets(html: str, base_dir: Path) -> str:
    def _script(m):
        src = m.group(1)
        p = base_dir / src
        if p.exists():
            return f"<script>{p.read_text(encoding='utf-8', errors='replace')}</script>"
        return m.group(0)

    def _style(m):
        href = m.group(1)
        p = base_dir / href
        if p.exists():
            return f"<style>{p.read_text(encoding='utf-8', errors='replace')}</style>"
        return m.group(0)

    html = re.sub(r'<script[^>]+src=["\']([^"\']+)["\'][^>]*></script>', _script, html)
    html = re.sub(
        r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)["\'][^>]*/?>',
        _style, html,
    )
    return html


NODE_MESSAGES = {
    "planner":  ("🧠", "Planning your project…",       "Got it! I've analysed your request and built a plan."),
    "architect": ("📐", "Designing the architecture…", "Architecture ready — breaking the work into tasks."),
    "coder":    ("💻", "Writing code…",                 None),  # dynamic per file
}


def run_agent_in_thread(prompt: str, limit: int, q: queue.Queue):
    """Streams langgraph node events into q as (kind, payload) tuples."""
    # Suppress all stdout/stderr noise from langchain
    import os, io
    devnull = open(os.devnull, "w", encoding="utf-8")
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = devnull
    sys.stderr = devnull

    try:
        from agent.graph import agent

        prev_node = None
        coder_step = 0

        for event in agent.stream(
            {"user_prompt": prompt},
            {"recursion_limit": limit},
            stream_mode="updates",
        ):
            node = next(iter(event))
            state = event[node]

            if node != prev_node:
                prev_node = node
                icon, thinking, done = NODE_MESSAGES.get(node, ("⚙️", f"Running {node}…", None))

                if node == "coder":
                    task_plan = state.get("task_plan") or (
                        state.get("coder_state") and state["coder_state"].task_plan
                    )
                    steps = task_plan.implementation_steps if task_plan else []
                    coder_step_idx = (state.get("coder_state") and state["coder_state"].current_step_idx - 1) or coder_step
                    coder_step += 1
                    if steps and 0 <= coder_step_idx < len(steps):
                        filepath = steps[coder_step_idx].filepath
                        done = f"Wrote `{filepath}`"
                    else:
                        done = f"Wrote file #{coder_step}"

                q.put(("thinking", (icon, thinking)))

            # when node output arrives, post the "done" message
            icon, _, done_msg = NODE_MESSAGES.get(node, ("⚙️", "", None))
            if node == "coder":
                cs = state.get("coder_state")
                if cs:
                    idx = cs.current_step_idx - 1
                    steps = cs.task_plan.implementation_steps
                    if 0 <= idx < len(steps):
                        done_msg = f"Wrote `{steps[idx].filepath}`"
                    else:
                        done_msg = f"Coding step complete."

            if done_msg:
                q.put(("done_step", (icon, done_msg)))

        # final state comes from last event
        last_state = state if 'state' in dir() else {}
        q.put(("finished", last_state))

    except Exception:
        q.put(("error", traceback.format_exc()))
    finally:
        sys.stdout = old_out
        sys.stderr = old_err
        devnull.close()


# ── chat display ──────────────────────────────────────────────────────────────

def render_messages():
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar=msg.get("avatar")):
            st.markdown(msg["content"])


render_messages()

# ── input bar ─────────────────────────────────────────────────────────────────
user_input = st.chat_input(
    "Describe the project you want to build…",
    disabled=st.session_state.running,
)

if user_input and not st.session_state.running:
    # show user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.running = True
    st.session_state.result = None
    st.rerun()

# ── agent loop ────────────────────────────────────────────────────────────────
if st.session_state.running:
    # the last message in state is the user prompt
    prompt = next(
        (m["content"] for m in reversed(st.session_state.messages) if m["role"] == "user"),
        "",
    )

    q: queue.Queue = queue.Queue()
    thread = threading.Thread(
        target=run_agent_in_thread,
        args=(prompt, recursion_limit, q),
        daemon=True,
    )
    thread.start()

    # live "thinking" bubble
    with st.chat_message("assistant", avatar="🤖"):
        status_placeholder = st.empty()
        status_placeholder.markdown("_Thinking…_")

    while thread.is_alive() or not q.empty():
        try:
            kind, payload = q.get(timeout=0.4)
        except queue.Empty:
            continue

        if kind == "thinking":
            icon, text = payload
            status_placeholder.markdown(f"{icon} _{text}_")

        elif kind == "done_step":
            icon, text = payload
            st.session_state.messages.append({
                "role": "assistant",
                "avatar": "🤖",
                "content": f"{icon} {text}",
            })

        elif kind == "finished":
            state = payload
            plan = state.get("plan")
            task_plan = state.get("task_plan")

            summary_lines = ["**Your project is ready!** Here's what was built:\n"]
            if plan:
                summary_lines.append(f"**{plan.name}** — {plan.description}")
                summary_lines.append(f"**Tech stack:** `{plan.techstack}`")
                summary_lines.append("\n**Features:**")
                for f in plan.features:
                    summary_lines.append(f"- {f}")
            if task_plan:
                summary_lines.append(f"\n**{len(task_plan.implementation_steps)} files generated.**")

            st.session_state.messages.append({
                "role": "assistant",
                "avatar": "🤖",
                "content": "\n".join(summary_lines),
            })
            st.session_state.result = state
            st.session_state.running = False
            break

        elif kind == "error":
            st.session_state.messages.append({
                "role": "assistant",
                "avatar": "🤖",
                "content": f"❌ Something went wrong:\n```\n{payload}\n```",
            })
            st.session_state.running = False
            break

    st.rerun()

# ── results (preview + file viewer) ──────────────────────────────────────────
if st.session_state.result is not None and not st.session_state.running:
    root = Path.cwd() / "generated_project"
    files = list_generated_files()

    if files:
        st.divider()
        html_files = [f for f in files if Path(f).suffix.lower() in PREVIEW_EXTENSIONS]
        react = is_react_project(files)

        if html_files or react:
            st.subheader("Preview")
            if react:
                index = root / "index.html"
                if index.exists():
                    html = inline_assets(index.read_text(encoding="utf-8", errors="replace"), root)
                    components.html(html, height=620, scrolling=True)
                else:
                    st.info("React project detected — run `npm install && npm run build` inside `generated_project/` to see the preview.")
            else:
                pick = st.selectbox("HTML file to preview", html_files, key="preview_pick")
                if pick:
                    raw = (root / pick).read_text(encoding="utf-8", errors="replace")
                    html = inline_assets(raw, (root / pick).parent)
                    components.html(html, height=620, scrolling=True)

        st.divider()
        st.subheader("View source")
        chosen = st.selectbox("File", files, key="src_pick")
        if chosen:
            content = (root / chosen).read_text(encoding="utf-8", errors="replace")
            ext = Path(chosen).suffix.lstrip(".")
            st.code(content, language=ext or "text")
