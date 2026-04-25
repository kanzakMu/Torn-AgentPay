from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def render_claude_startup_card_demo(
    *,
    repository_root: str | Path | None = None,
    card_file: str | Path | None = None,
    theme_file: str | Path | None = None,
    output_file: str | Path | None = None,
) -> str:
    repo_root = Path(repository_root or Path(__file__).resolve().parents[2]).resolve()
    if not repo_root.exists():
        repo_root = Path(__file__).resolve().parents[2]
    card_path = Path(card_file or repo_root / "agent-dist" / "assets" / "startup-card" / "example.startup_card.json").resolve()
    theme_path = Path(theme_file or repo_root / "agent-dist" / "assets" / "startup-card" / "theme.tokens.json").resolve()

    card = json.loads(card_path.read_text(encoding="utf-8"))
    theme = json.loads(theme_path.read_text(encoding="utf-8"))
    tone = str(card.get("tone", "info"))
    tone_theme = theme["tones"][tone]
    icon_path = theme_path.parent / tone_theme["icon"]
    icon_svg = icon_path.read_text(encoding="utf-8")

    checklist_items = "\n".join(f"<li>{_escape(item)}</li>" for item in card.get("checklist", []))
    resource_links = "\n".join(
        f'<a class="resource" href="{_escape(item["url"])}">{_escape(item["label"])}</a>'
        for item in card.get("resources", [])
    )
    secondary_actions = "\n".join(
        f'<button class="secondary">{_escape(item["label"])}</button>' for item in card.get("secondary_actions", [])
    )
    primary_action = card.get("primary_action", {})
    status = card.get("status", {})
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AimiPay Claude Startup Card Demo</title>
  <style>
    :root {{
      --card-bg: {tone_theme["background"]};
      --card-border: {tone_theme["border"]};
      --card-text: {tone_theme["text"]};
      --card-radius: {int(theme["layout"]["radius_px"])}px;
      --card-padding: {int(theme["layout"]["padding_px"])}px;
      --card-gap: {int(theme["layout"]["gap_px"])}px;
      --title-size: {int(theme["layout"]["title_size_px"])}px;
      --body-size: {int(theme["layout"]["body_size_px"])}px;
      --font-stack: {theme["brand"]["font_stack"]};
    }}
    body {{
      margin: 0;
      background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
      font-family: var(--font-stack);
      color: #0f172a;
      display: grid;
      place-items: center;
      min-height: 100vh;
      padding: 32px;
    }}
    .frame {{
      width: min(820px, 100%);
      background: rgba(255,255,255,0.72);
      border: 1px solid rgba(148,163,184,0.25);
      border-radius: 24px;
      box-shadow: 0 24px 80px rgba(15, 23, 42, 0.12);
      backdrop-filter: blur(16px);
      overflow: hidden;
    }}
    .host-bar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 14px 18px;
      background: #111827;
      color: #f8fafc;
      font-size: 13px;
      letter-spacing: 0.02em;
    }}
    .content {{
      padding: 28px;
      display: grid;
      gap: 18px;
    }}
    .eyebrow {{
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #475569;
    }}
    .card {{
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 18px;
      padding: var(--card-padding);
      border-radius: var(--card-radius);
      border: 2px solid var(--card-border);
      background: var(--card-bg);
      color: var(--card-text);
    }}
    .icon {{
      width: 72px;
      height: 72px;
      display: grid;
      place-items: center;
      background: rgba(255,255,255,0.6);
      border-radius: 18px;
      overflow: hidden;
    }}
    .icon svg {{
      width: 56px;
      height: 56px;
    }}
    .title {{
      font-size: var(--title-size);
      font-weight: 700;
      margin: 0 0 8px 0;
    }}
    .summary {{
      font-size: var(--body-size);
      line-height: 1.5;
      margin: 0 0 14px 0;
    }}
    .actions {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }}
    .primary, .secondary {{
      border: 0;
      border-radius: 999px;
      padding: 10px 16px;
      font-size: 14px;
      font-weight: 600;
      cursor: default;
    }}
    .primary {{
      background: #0f172a;
      color: #f8fafc;
    }}
    .secondary {{
      background: rgba(255,255,255,0.72);
      color: #0f172a;
      border: 1px solid rgba(15,23,42,0.08);
    }}
    .details {{
      display: grid;
      gap: 12px;
      grid-template-columns: 1fr 1fr;
    }}
    .panel {{
      background: rgba(255,255,255,0.58);
      border-radius: 16px;
      padding: 14px;
    }}
    .panel h3 {{
      margin: 0 0 10px 0;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #475569;
    }}
    ul {{
      margin: 0;
      padding-left: 18px;
      display: grid;
      gap: 8px;
    }}
    .resources {{
      display: grid;
      gap: 10px;
    }}
    .resource {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      text-decoration: none;
      color: #0f172a;
      background: rgba(255,255,255,0.7);
      border: 1px solid rgba(15,23,42,0.08);
      border-radius: 12px;
      padding: 10px 12px;
    }}
    .status {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 12px;
      font-weight: 700;
      background: rgba(15,23,42,0.08);
      color: #334155;
    }}
    @media (max-width: 720px) {{
      .card {{
        grid-template-columns: 1fr;
      }}
      .details {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
    <body>
      <div class="frame">
        <div class="host-bar">
          <span>Claude Desktop - AimiPay MCP Connected</span>
          <span>{_escape(card.get("schema_version", ""))}</span>
        </div>
    <div class="content">
      <div class="eyebrow">Recommended First-Screen Onboarding</div>
      <section class="card">
        <div class="icon">{icon_svg}</div>
            <div>
              <h1 class="title">{_escape(card.get("title", ""))}</h1>
              <p class="summary">{_escape(card.get("summary", ""))}</p>
              <div class="actions">
                <button class="primary">{_escape(primary_action.get("label", "Continue"))}</button>
                {secondary_actions}
              </div>
              <div class="status">
                <span class="pill">Tone: {_escape(card.get("tone", ""))}</span>
                <span class="pill">Next Step: {_escape(status.get("next_step", ""))}</span>
                <span class="pill">Visible: {_escape(str(card.get("visible", False)).lower())}</span>
              </div>
            </div>
      </section>
      <section class="details">
        <div class="panel">
          <h3>Checklist</h3>
          <ul>{checklist_items}</ul>
        </div>
        <div class="panel">
          <h3>Resources</h3>
          <div class="resources">{resource_links}</div>
        </div>
      </section>
    </div>
  </div>
</body>
</html>
"""
    if output_file is not None:
        output_path = Path(output_file).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
    return html


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a Claude-style startup onboarding card demo for AimiPay.")
    parser.add_argument("--repository-root")
    parser.add_argument("--card-file")
    parser.add_argument("--theme-file")
    parser.add_argument("--output-file")
    args = parser.parse_args(argv)

    html = render_claude_startup_card_demo(
        repository_root=args.repository_root,
        card_file=args.card_file,
        theme_file=args.theme_file,
        output_file=args.output_file,
    )
    if not args.output_file:
        print(html)
    return 0


def _escape(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


if __name__ == "__main__":
    raise SystemExit(main())
