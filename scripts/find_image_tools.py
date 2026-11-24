#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""List the image-generation tools this machine could use, so the owner can be asked for permission (stage 0).
Detection only: it calls no API, spends nothing, and never reads or prints a key's value. Standard library only.

  python find_image_tools.py [--out image-tools-found.json]

It checks three places:
  1. command-line tools on PATH (for example the Codex CLI or the Gemini CLI);
  2. environment variables that NAME a key (for example OPENROUTER_API_KEY): presence only;
  3. Python packages of image providers.
It cannot see the agent's own connectors: the agent must also look through its own tool list for image tools
(names with "image" or "generate"), such as an OpenRouter or a media-studio connector.
Nothing found here may be used before the owner says yes: references/15-image-tools.md"""
import argparse
import importlib.util
import json
import os
import shutil
import sys

CLIS = [
    ('codex', 'Codex CLI', 'can create images from inside a Codex session when its image tool is enabled in this version'),
    ('gemini', 'Gemini CLI', 'can create images when an image model is enabled for the account'),
    ('openai', 'OpenAI CLI', 'image endpoints through the account behind OPENAI_API_KEY'),
    ('higgsfield', 'Higgsfield CLI', 'image and video models of the signed-in account'),
    ('replicate', 'Replicate CLI', 'hosted image models through REPLICATE_API_TOKEN'),
    ('comfy', 'ComfyUI CLI', 'local image models on this machine (no per-image fee, needs a GPU)'),
]
ENV = [
    ('OPENROUTER_API_KEY', 'OpenRouter', 'many image models behind one key; price is per image and differs by model'),
    ('OPENAI_API_KEY', 'OpenAI', 'OpenAI image models'),
    ('GEMINI_API_KEY', 'Google Gemini', 'Gemini / Imagen image models'),
    ('GOOGLE_API_KEY', 'Google', 'Gemini / Imagen image models'),
    ('FAL_KEY', 'fal', 'hosted image models'),
    ('REPLICATE_API_TOKEN', 'Replicate', 'hosted image models'),
    ('STABILITY_API_KEY', 'Stability', 'Stable Diffusion models'),
    ('HF_TOKEN', 'Hugging Face', 'hosted inference for open image models'),
]
PACKAGES = [('openai', 'openai'), ('google.genai', 'google-genai'), ('replicate', 'replicate'), ('fal_client', 'fal-client'),
            ('diffusers', 'diffusers (local models)')]


def has_package(mod):
    try:
        return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out')
    a = ap.parse_args()
    found = []
    for exe, name, note in CLIS:
        path = shutil.which(exe)
        if path:
            found.append({'tool': name, 'kind': 'cli', 'detected': f'`{exe}` on PATH', 'note': note})
    for var, name, note in ENV:
        if os.environ.get(var):
            found.append({'tool': name, 'kind': 'api-key', 'detected': f'environment variable {var} is set (value not read)', 'note': note})
    for mod, label in PACKAGES:
        if has_package(mod):
            found.append({'tool': label, 'kind': 'python-package', 'detected': f'Python package `{mod}` is installed',
                          'note': 'a library only: it still needs a key or a local model'})
    report = {'found': found,
              'not_checked': 'the agent\'s own connectors and MCP tools: look through your tool list for image tools',
              'rule': 'ask the owner before the first image: tool, purpose, cost cap, what is sent out (references/15-image-tools.md)'}
    if a.out:
        with open(a.out, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
            f.write('\n')
    usable = [x for x in found if x['kind'] != 'python-package']
    print(f'image tools on this machine: {len(usable)} candidate(s)' + (f', plus {len(found) - len(usable)} library(ies)' if len(found) > len(usable) else ''))
    for x in found:
        print(f"  - {x['tool']} [{x['kind']}]: {x['detected']}. {x['note']}")
    print('\nalso look through YOUR OWN tool list (connectors / MCP) for image tools: this script cannot see them.')
    if usable:
        print('-> none of these may be used yet. Ask the owner: which tool, for what, the weekly cost cap, and that only')
        print('   text prompts are sent out. Then make ONE test image and show it (references/15-image-tools.md).')
    else:
        print('-> no image tool found here. Design with code and the brand\'s real photos, and tell the owner which tool')
        print('   would add generated images if they choose to enable one (references/15-image-tools.md).')
    if a.out:
        print('saved:', a.out)


if __name__ == '__main__':
    main()
