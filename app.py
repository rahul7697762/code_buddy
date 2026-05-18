import sys
import threading
import queue
import traceback
from io import StringIO
from pathlib import Path

import streamlit.components.v1 as components

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Coder Buddy",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 Coder Buddy")
st.caption("Describe your project and let the AI plan, architect, and code it for you.")

# ── sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    recursion_limit = st.slider("Recursion limit", 10, 300, 100, step=10)
    st.divider()
    st.markdown("**Generated files** will appear in `./generated_project/`")
    if st.button("Open generated_project folder"):
        import subprocess, os
        folder = Path.cwd() / "generated_project"
        folder.mkdir(exist_ok=True)
        subprocess.Popen(f'explorer "{folder}"')

# ── main input ────────────────────────────────────────────────────────────────
user_prompt = st.text_area(
    "What would you like to build?",
    placeholder="e.g. Build a colourful modern todo app in HTML, CSS, and JS",
    height=120,
)

run_btn = st.button("Generate Project", type="primary", disabled=not user_prompt.strip())

# ── helpers ───────────────────────────────────────────────────────────────────

def run_agent_in_thread(prompt: str, limit: int, log_queue: queue.Queue):
    """Runs the langgraph agent in a background thread, streaming stdout to log_queue."""
    old_stdout = sys.stdout
    old_stderr = sys.stderr

    class QueueWriter(StringIO):
        def write(self, text):
            if text.strip():
                log_queue.put(("log", text))

    sys.stdout = QueueWriter()
    sys.stderr = QueueWriter()
    try:
        from agent.graph import agent
        result = agent.invoke(
            {"user_prompt": prompt},
            {"recursion_limit": limit},
        )
        log_queue.put(("done", result))
    except Exception:
        log_queue.put(("error", traceback.format_exc()))
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


def list_generated_files() -> list[str]:
    root = Path.cwd() / "generated_project"
    if not root.exists():
        return []
    return sorted(str(f.relative_to(root)) for f in root.rglob("*") if f.is_file())


PREVIEW_EXTENSIONS = {".html", ".htm"}
REACT_INDICATORS = {"jsx", "tsx", "react", "vite", "next"}


def is_react_project(files: list[str]) -> bool:
    all_text = " ".join(files).lower()
    return any(ind in all_text for ind in REACT_INDICATORS)


def build_react_preview(root: Path) -> str | None:
    """Inline all JS/CSS into the index.html so we can render it without a server."""
    index = root / "index.html"
    if not index.exists():
        return None

    html = index.read_text(encoding="utf-8", errors="replace")

    # Replace <script src="..."> with inline <script>
    import re
    def inline_script(m):
        src = m.group(1)
        js_path = root / src.lstrip("/")
        if js_path.exists():
            code = js_path.read_text(encoding="utf-8", errors="replace")
            return f"<script>{code}</script>"
        return m.group(0)

    def inline_style(m):
        href = m.group(1)
        css_path = root / href.lstrip("/")
        if css_path.exists():
            code = css_path.read_text(encoding="utf-8", errors="replace")
            return f"<style>{code}</style>"
        return m.group(0)

    html = re.sub(r'<script[^>]+src=["\']([^"\']+)["\'][^>]*></script>', inline_script, html)
    html = re.sub(r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)["\'][^>]*/?>',
                  inline_style, html)
    return html


# ── run ───────────────────────────────────────────────────────────────────────
if run_btn:
    st.divider()
    col_log, col_files = st.columns([3, 2])

    with col_log:
        st.subheader("Live log")
        log_box = st.empty()
        status_box = st.empty()

    with col_files:
        st.subheader("Generated files")
        files_box = st.empty()

    log_lines: list[str] = []
    q: queue.Queue = queue.Queue()

    thread = threading.Thread(
        target=run_agent_in_thread,
        args=(user_prompt.strip(), recursion_limit, q),
        daemon=True,
    )
    thread.start()

    status_box.info("Agent is running…")

    while thread.is_alive() or not q.empty():
        try:
            kind, payload = q.get(timeout=0.3)
        except queue.Empty:
            # refresh file list while waiting
            files = list_generated_files()
            if files:
                files_box.markdown("\n".join(f"- `{f}`" for f in files))
            continue

        if kind == "log":
            log_lines.append(payload.rstrip())
            log_box.code("\n".join(log_lines[-120:]), language="text")

        elif kind == "done":
            result = payload
            status_box.success("Project generated successfully!")

            # show plan summary if available
            plan = result.get("plan")
            task_plan = result.get("task_plan")
            if plan:
                with st.expander("Plan", expanded=True):
                    st.markdown(f"**{plan.name}** — {plan.description}")
                    st.markdown(f"**Tech stack:** {plan.techstack}")
                    st.markdown("**Features:**")
                    for feat in plan.features:
                        st.markdown(f"- {feat}")

            if task_plan:
                with st.expander("Implementation steps", expanded=False):
                    for i, step in enumerate(task_plan.implementation_steps, 1):
                        st.markdown(f"**{i}. `{step.filepath}`**")
                        st.markdown(step.task_description)

        elif kind == "error":
            status_box.error("An error occurred.")
            st.code(payload, language="text")

    # final file list
    files = list_generated_files()
    root = Path.cwd() / "generated_project"
    if files:
        files_box.markdown("\n".join(f"- `{f}`" for f in files))

        # ── preview section ──────────────────────────────────────────────────
        html_files = [f for f in files if Path(f).suffix.lower() in PREVIEW_EXTENSIONS]
        if html_files or is_react_project(files):
            st.divider()
            st.subheader("Preview")

            if is_react_project(files):
                inlined = build_react_preview(root)
                if inlined:
                    components.html(inlined, height=600, scrolling=True)
                else:
                    st.info(
                        "React project detected. Run `npm install && npm run build` "
                        "inside `generated_project/`, then reopen the app to see the preview."
                    )
            elif html_files:
                preview_file = st.selectbox(
                    "Choose HTML file to preview",
                    html_files,
                    key="preview_select",
                )
                if preview_file:
                    html_content = (root / preview_file).read_text(
                        encoding="utf-8", errors="replace"
                    )

                    # Inline linked CSS/JS relative to the HTML file
                    import re
                    html_dir = (root / preview_file).parent

                    def _inline_script(m):
                        src = m.group(1)
                        p = html_dir / src
                        if p.exists():
                            return f"<script>{p.read_text(encoding='utf-8', errors='replace')}</script>"
                        return m.group(0)

                    def _inline_style(m):
                        href = m.group(1)
                        p = html_dir / href
                        if p.exists():
                            return f"<style>{p.read_text(encoding='utf-8', errors='replace')}</style>"
                        return m.group(0)

                    html_content = re.sub(
                        r'<script[^>]+src=["\']([^"\']+)["\'][^>]*></script>',
                        _inline_script, html_content,
                    )
                    html_content = re.sub(
                        r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)["\'][^>]*/?>',
                        _inline_style, html_content,
                    )
                    components.html(html_content, height=600, scrolling=True)

        # ── file viewer ──────────────────────────────────────────────────────
        st.divider()
        st.subheader("View source")
        chosen = st.selectbox("Pick a file", files)
        if chosen:
            content = (root / chosen).read_text(encoding="utf-8", errors="replace")
            ext = Path(chosen).suffix.lstrip(".")
            st.code(content, language=ext or "text")
