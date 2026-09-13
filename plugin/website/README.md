# Finrun public website

Live: https://finrun.ickma2311.workers.dev/ (Cloudflare Worker `finrun`).
The landing page and setup instructions describe published version 0.5.0-preview.2.
The privacy, terms and support pages are rendered from `plugin/policies/`;
the privacy page also describes this static website's hosting and clipboard use.

This source was brought into the repository from
`/Users/chaoma/Documents/ChatGPT/chao/FinRunbook-landing-demo`.
That original directory remains unchanged. The historical reports and workbook
were already public; they are copied byte-for-byte into the build and are
explicitly labeled as earlier examples. No new research runs are published.

Build to a new ignored directory:

```sh
python3 plugin/website/build.py \
  --previous-site /Users/chaoma/Documents/ChatGPT/chao/FinRunbook-landing-demo/dist \
  --output run/.build/website-0.5
```

Use the previous deployed `dist` (or a preserved copy) for `--previous-site`.
Only the two named historical reports and the NVIDIA workbook are imported.
`preserved-examples.json` records their hashes. Website source, dependencies,
plugin archives and research runs are not included in the public asset directory.

From the output directory, run the link check with
`node ../../../plugin/website/check-site.mjs`, then run
`wrangler deploy --config wrangler.jsonc --dry-run` and inspect the site in a
browser. Publish with `wrangler deploy --config wrangler.jsonc` when authorized.
The generated config targets the existing Worker and preserves its static
HTML routing. Do not deploy `finrun-mcp-preview`, which is a separate service.
