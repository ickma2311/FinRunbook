"""Build the website while preserving only the previously published examples."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import shutil

HERE = Path(__file__).resolve().parent


def inline(text):
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    for name in ("support", "privacy", "terms"):
        text = text.replace(f"{name}-0.5.md", f"/{name}/")
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)


def policy_page(markdown):
    # The versioned policy sources use headings and paragraphs only.
    blocks = []
    for block in markdown.strip().split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("# "):
            blocks.append(f"<h1>{inline(block[2:])}</h1>")
        elif block.startswith("## "):
            blocks.append(f"<h2>{inline(block[3:])}</h2>")
        else:
            blocks.append(f"<p>{inline(' '.join(block.splitlines()))}</p>")
    title = html.escape(markdown.splitlines()[0].removeprefix("# "))
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><link rel="icon" href="/favicon.svg"><link rel="stylesheet" href="/style.css?v=050"><link rel="stylesheet" href="/release.css?v=050"></head><body><header class="nav wrap"><a class="brand" href="/"><span class="mark">F</span>Finrun</a><nav class="legal-nav"><a href="/setup/">Setup</a><a href="/support/">Support</a></nav></header><main class="legal wrap">{''.join(blocks)}</main><footer class="wrap"><a href="/">Finrun</a><a href="/support/">Support</a><a href="/privacy/">Privacy</a><a href="/terms/">Terms</a></footer></body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-site", required=True, type=Path, help="Previous public dist directory; examples are copied byte-for-byte")
    parser.add_argument("--output", required=True, type=Path, help="A new build directory under run/")
    args = parser.parse_args()
    output = args.output.resolve()
    run = HERE.parents[1] / "run"
    if not output.is_relative_to(run) or output.exists():
        parser.error("Output must be a new directory under this repository's run/")
    frozen = [
        Path("examples/apple-business-quality"),
        Path("examples/cloud-computing"),
        Path("assets/NVIDIA_FY2000-FY2026_Latest_Interim.xlsx"),
    ]
    for relative in frozen:
        if not (args.previous_site / relative).exists():
            parser.error(f"Missing previously published asset: {relative}")
    dist = output / "dist"
    shutil.copytree(HERE / "public", dist)
    hashes = {}
    for relative in frozen:
        src, dest = args.previous_site / relative, dist / relative
        if src.is_dir():
            shutil.copytree(src, dest)
            files = [p for p in src.rglob("*") if p.is_file()]
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            files = [src]
        for file in files:
            key = file.relative_to(args.previous_site)
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            assert digest == hashlib.sha256((dist / key).read_bytes()).hexdigest()
            hashes[str(key)] = digest
    for name in ("privacy", "terms", "support"):
        source = (HERE.parent / "policies" / f"{name}-0.5.md").read_text()
        if name == "privacy":
            source += '\n\n## This website\n\nCloudflare hosts this static website and handles requests for its pages and downloads, including ordinary network information such as IP addresses and request headers. See the [Cloudflare privacy policy](https://www.cloudflare.com/privacypolicy/). This website does not execute research or collect prompts. Editing an example prompt stays in your browser; Copy prompt uses your clipboard. No custom analytics, advertising trackers, account or payment form is included.\n'
        (dist / name).mkdir(parents=True, exist_ok=True)
        (dist / name / "index.html").write_text(policy_page(source))
    config = json.loads((HERE / "wrangler.jsonc").read_text())
    config["assets"]["directory"] = "./dist"
    (output / "wrangler.jsonc").write_text(json.dumps(config, indent=2) + "\n")
    (output / "preserved-examples.json").write_text(json.dumps(hashes, indent=2) + "\n")
    print(output)


if __name__ == "__main__":
    main()
