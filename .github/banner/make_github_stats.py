"""Generates github-stats.svg for the "Github Stats" section of the profile README.

Counts merged pull requests in other people's open-source repositories and draws them by area,
by language of the changed code, and by framework. Animated once on load (CSS, no loop);
transparent background and theme-neutral colours, so one file works in light and dark themes.

Run from the repo root (needs an authenticated `gh` CLI):
    python .github/banner/make_github_stats.py

Data:
- GitHub: `gh search prs --author <AUTHOR> --merged`, minus own repos (OWN_PREFIXES); changed files
  of every PR via the REST API.
- Gitea (not visible to GitHub search): the PRs in GITEA_PRS are checked through the Gitea API on
  every run (must be merged); their files come from the merge-commit diff, because the PR stats on
  that instance were recomputed after its 2026-11 restore and are wrong.
- Areas: AREAS maps each repo to one row; a repo missing there stops the script.
- Languages: added + deleted lines of code files by extension (docs, config and lock files excluded).
- Frameworks: path rules per repo in classify(); test frameworks are not counted.

Needs: Python 3 with Pillow (text-width estimates with the Windows font Segoe UI).
"""
import collections
import json
import os
import re
import subprocess
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html import escape

from PIL import ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(REPO, "github-stats.svg")
AUTHOR = "TheSeydiCharyyev"
OWN_PREFIXES = ("TheSeydiCharyyev/", "Shapak-Apps/")
GITEA = "https://gitea.coracle.social"
GITEA_PRS = [("coracle/flotilla", 385), ("coracle/flotilla", 652), ("coracle/flotilla", 858),
             ("coracle/welshman", 118)]

# (name, subtitle, colour, repos); rows are drawn sorted by PR count
AREAS = [
    ("Freedom Tech", "(Bitcoin, Lightning, Nostr)", "#f7931a", [
        "ZeusLN/zeus", "aljazceru/awesome-nostr", "divinevideo/divine-web", "divinevideo/divine-moderation-service",
        "divinevideo/divine-name-server", "nostr-protocol/nips", "nbd-wtf/nostr-tools", "VectorPrivacy/Vector",
        "gitea:coracle/flotilla", "gitea:coracle/welshman"]),
    ("React Foundation", "", "#3b8eea", [
        "storybookjs/storybook", "expo/expo", "thereactfoundation/react.foundation", "ant-design/ant-design"]),
    ("Web & mobile", "", "#e5534b", [
        "pmndrs/zustand", "dogankaraarslan1/ciaorelated", "supabase/supabase-js", "supabase/ssr", "TanStack/query",
        "callstackincubator/react-native-harness", "medusajs/medusa", "calcom/cal.diy",
        "Permissionless-Software-Foundation/psf-bch-api", "Permissionless-Software-Foundation/fulcrum-api"]),
    ("AI agents", "", "#a371f7", [
        "aaif-goose/goose", "ag-ui-protocol/ag-ui", "agentgateway/agentgateway", "agentgateway/website",
        "modelcontextprotocol/rust-sdk", "block/buzz"]),
    ("Identity", "", "#2ea043", [
        "hyperledger-identus/identity-portal", "hyperledger-identus/sdk-ts", "hyperledger-identus/cloud-agent"]),
    ("Education", "", "#db61a2", ["freeCodeCamp/freeCodeCamp", "mdn/content"]),
]

LANG = {".ts": "TypeScript", ".tsx": "TypeScript", ".py": "Python", ".rs": "Rust", ".js": "JavaScript",
        ".mjs": "JavaScript", ".jsx": "JavaScript"}
LANG_COLOR = {"TypeScript": "#3178c6", "Python": "#3fb8af", "Rust": "#dea584", "JavaScript": "#e6c619"}
CODE = tuple(LANG)

# frameworks of a repo's code PRs (checked against the repos' manifests)
REPO_STACK = {
    "ZeusLN/zeus": ["React Native"],
    "storybookjs/storybook": ["React"],
    "thereactfoundation/react.foundation": ["Next.js", "React"],
    "agentgateway/agentgateway": ["React"],
    "divinevideo/divine-web": ["React"],
    "dogankaraarslan1/ciaorelated": ["React Native", "Expo"],
    "callstackincubator/react-native-harness": ["React Native"],
    "modelcontextprotocol/rust-sdk": ["Tokio"],
    "VectorPrivacy/Vector": ["Tokio"],
    "Permissionless-Software-Foundation/fulcrum-api": ["Express"],
    "Permissionless-Software-Foundation/psf-bch-api": ["Express"],
    "divinevideo/divine-name-server": ["Hono", "React"],
    "medusajs/medusa": ["React"],
}
AG_UI = {"aws-strands": "AWS Strands", "langgraph": "LangGraph", "langchain": "LangChain",
         "mastra": "Mastra", "vercel-ai-sdk": "Vercel AI SDK"}


def ext(path):
    base = path.rsplit("/", 1)[-1]
    return "." + base.rsplit(".", 1)[-1].lower() if "." in base else ""


def classify(p):
    """Frameworks touched by a PR; None when the PR changes no code at all."""
    code = [x["f"] for x in p["files"] if x["f"].endswith(CODE)]
    if not code:
        return None
    repo, fw = p["repo"], set()
    if repo == "hyperledger-identus/identity-portal":
        for f in code:
            if f.startswith(("src/ui", "apps/portal")):
                fw.add("React")
            if f.startswith(("src/api", "src/main.ts")):
                fw.add("Express")
    elif repo == "aaif-goose/goose":
        for f in code:
            if f.startswith("ui/desktop"):
                fw.update(["Electron", "React"])
            if f.startswith("crates/"):
                fw.add("Tokio")
    elif repo == "ag-ui-protocol/ag-ui":
        for f in code:
            parts = f.split("/")
            if parts[0] == "integrations" and len(parts) > 1 and parts[1] in AG_UI:
                fw.add(AG_UI[parts[1]])
    else:
        fw.update(REPO_STACK.get(repo, []))
    return sorted(fw)


# ---------------------------------------------------------------- data
def gh(args):
    r = subprocess.run(["gh"] + args, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise RuntimeError(f"gh {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def github_prs():
    found = json.loads(gh(["search", "prs", "--author", AUTHOR, "--merged", "--limit", "1000",
                           "--json", "repository,number"]))
    found = [p for p in found if not p["repository"]["nameWithOwner"].startswith(OWN_PREFIXES)]

    def files(p):
        repo = p["repository"]["nameWithOwner"]
        out = gh(["api", "--paginate", f"repos/{repo}/pulls/{p['number']}/files",
                  "--jq", '.[] | [.filename, .additions, .deletions] | @tsv'])
        rows = [line.split("\t") for line in out.splitlines()]
        return {"repo": repo, "files": [{"f": f, "a": int(a), "d": int(d)} for f, a, d in rows]}

    with ThreadPoolExecutor(8) as ex:
        return list(ex.map(files, found))


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "profile-stats-script"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def gitea_prs():
    result = []
    for repo, number in GITEA_PRS:
        pr = json.loads(http_get(f"{GITEA}/api/v1/repos/{repo}/pulls/{number}"))
        if not pr.get("merged"):
            raise RuntimeError(f"{GITEA}/{repo}/pulls/{number} is not merged")
        diff = http_get(f"{GITEA}/api/v1/repos/{repo}/git/commits/{pr['merge_commit_sha']}.diff")
        lines, cur = collections.defaultdict(lambda: [0, 0]), None
        for line in diff.splitlines():
            m = re.match(r"^diff --git a/(\S+) b/", line)
            if m:
                cur = m.group(1)
            elif cur and line.startswith("+") and not line.startswith("+++"):
                lines[cur][0] += 1
            elif cur and line.startswith("-") and not line.startswith("---"):
                lines[cur][1] += 1
        result.append({"repo": f"gitea:{repo}", "files": [{"f": f, "a": a, "d": d} for f, (a, d) in lines.items()]})
    return result


prs = github_prs() + gitea_prs()
repos = {p["repo"] for p in prs}
area_of = {r: i for i, (_, _, _, rs) in enumerate(AREAS) for r in rs}
missing = repos - set(area_of)
if missing:
    raise SystemExit(f"add these repos to AREAS first: {sorted(missing)}")

area_n, lang, fw = collections.Counter(), collections.Counter(), collections.Counter()
for p in prs:
    area_n[area_of[p["repo"]]] += 1
    for x in p["files"]:
        if ext(x["f"]) in LANG:
            lang[LANG[ext(x["f"])]] += x["a"] + x["d"]
    fw.update(classify(p) or [])
total_lines = sum(lang.values())
lang_pct = [(k, v / total_lines * 100) for k, v in lang.most_common()]

# ---------------------------------------------------------------- drawing
F = {s: ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", s) for s in (12, 13, 14)}
FB = {s: ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", s) for s in (13, 14, 18, 44)}


def tw(text, size, bold=False):
    return (FB if bold else F)[size].getlength(text)


def fade(delay):
    return f'class="f" style="animation-delay:{delay:.2f}s"'


W = 840
MUTED = "#7d8590"
TEXT = "#848d97"
el = []

nx = tw(str(len(prs)), 44, True) + 12
el.append(f'<g {fade(0)}>'
          f'<text x="0" y="46" class="num">{len(prs)}</text>'
          f'<text x="{nx:.0f}" y="27" class="h">merged pull requests</text>'
          f'<text x="{nx:.0f}" y="46" class="sub">across {len(repos)} open-source repositories</text>'
          f'</g>')

y = 92
el.append(f'<g {fade(0.25)}><text x="0" y="{y}" class="cap">BY AREA</text></g>')
y += 24
max_n = max(area_n.values())
BAR_X = 200
BAR_W = W - BAR_X - 44
order = sorted(range(len(AREAS)), key=lambda i: -area_n[i])
for k, i in enumerate(order):
    name, subtitle, color, _ = AREAS[i]
    d = 0.35 + k * 0.12
    n = area_n[i]
    sub = f'<text x="0" y="{y + 17}" class="asub">{escape(subtitle)}</text>' if subtitle else ""
    el.append(f'<g {fade(d)}>'
              f'<text x="0" y="{y}" class="area" fill="{color}">{escape(name)}</text>{sub}'
              f'<rect x="{BAR_X}" y="{y - 9}" width="{BAR_W}" height="8" rx="4" class="track"/>'
              f'<rect x="{BAR_X}" y="{y - 9}" width="{BAR_W * n / max_n:.1f}" height="8" rx="4" fill="{color}" '
              f'class="bar" style="animation-delay:{d + 0.1:.2f}s"/>'
              f'<text x="{W}" y="{y}" class="cnt" text-anchor="end">{n}</text>'
              f'</g>')
    y += 50 if subtitle else 34

y += 14
d0 = 0.35 + len(AREAS) * 0.12 + 0.1
el.append(f'<g {fade(d0)}><text x="0" y="{y}" class="cap">LANGUAGES IN MERGED CODE</text></g>')
y += 14
x, seg = 0, []
for k, (name, pct) in enumerate(lang_pct):
    w = W * pct / 100
    seg.append(f'<rect x="{x:.1f}" y="{y}" width="{max(w - 2, 1):.1f}" height="8" fill="{LANG_COLOR[name]}" '
               f'class="bar" style="animation-delay:{d0 + 0.1 + k * 0.12:.2f}s"/>')
    x += w
el.append(f'<g>{"".join(seg)}</g>')
y += 30
x, leg = 0, []
for name, pct in lang_pct:
    label = f"{name} {pct:.0f}%"
    leg.append(f'<circle cx="{x + 5}" cy="{y - 4}" r="4.5" fill="{LANG_COLOR[name]}"/>'
               f'<text x="{x + 15}" y="{y}" class="leg">{label}</text>')
    x += 15 + tw(label, 13) + 26
el.append(f'<g {fade(d0 + 0.2)}>{"".join(leg)}</g>')

y += 34
d1 = d0 + 0.5
el.append(f'<g {fade(d1)}><text x="0" y="{y}" class="cap">FRAMEWORKS</text></g>')
y += 14
x, row_y, chips = 0, y, []
for k, (name, c) in enumerate(fw.most_common()):
    w = tw(name, 13) + tw(str(c), 13) + 30
    if x + w > W:
        x, row_y = 0, row_y + 36
    chips.append(f'<g {fade(d1 + 0.08 + k * 0.05)}>'
                 f'<rect x="{x:.1f}" y="{row_y}" width="{w:.1f}" height="26" rx="13" class="chip"/>'
                 f'<text x="{x + 12:.1f}" y="{row_y + 17.5}" class="leg">{escape(name)}'
                 f'<tspan class="cntc" dx="6">{c}</tspan></text></g>')
    x += w + 8
el.append("".join(chips))
H = row_y + 26 + 4

STYLE = f"""
text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif; }}
.num {{ font-size: 44px; font-weight: 700; fill: #3b8eea; }}
.h {{ font-size: 18px; font-weight: 600; fill: {TEXT}; }}
.sub {{ font-size: 13px; fill: {MUTED}; }}
.cap {{ font-size: 11px; font-weight: 600; letter-spacing: .12em; fill: {MUTED}; }}
.area {{ font-size: 14px; font-weight: 600; }}
.asub {{ font-size: 12px; fill: {MUTED}; }}
.cnt {{ font-size: 13px; font-weight: 700; fill: {TEXT}; }}
.leg {{ font-size: 13px; fill: {TEXT}; }}
.cntc {{ font-weight: 700; fill: {MUTED}; }}
.track {{ fill: {MUTED}; fill-opacity: .18; }}
.chip {{ fill: {MUTED}; fill-opacity: .10; stroke: {MUTED}; stroke-opacity: .35; }}
.f {{ animation: fadeUp .6s cubic-bezier(.2,.8,.2,1) both; }}
.bar {{ transform-box: fill-box; transform-origin: left center; animation: grow .9s cubic-bezier(.2,.8,.2,1) both; }}
@keyframes fadeUp {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: none; }} }}
@keyframes grow {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
@media (prefers-reduced-motion: reduce) {{ .f, .bar {{ animation: none; }} }}
"""
title = f"{len(prs)} merged pull requests across {len(repos)} open-source repositories"
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
       f'role="img" aria-labelledby="t"><title id="t">{title}</title>'
       f'<style>{STYLE}</style>{"".join(el)}</svg>\n')
with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    fh.write(svg)
print(f"{OUT}: {title}")
print("areas:", {AREAS[i][0]: area_n[i] for i in order})
print("languages:", [(k, round(v, 1)) for k, v in lang_pct])
print("frameworks:", dict(fw.most_common()))
