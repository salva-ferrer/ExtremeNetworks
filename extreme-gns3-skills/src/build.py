#!/usr/bin/env python3
"""Build dist/extreme-gns3-skills.zip and dist/extreme-gns3-skills-guide.{html,pdf}.

Needs pandoc and weasyprint. Run from anywhere: python3 src/build.py
"""
import datetime
import pathlib
import re
import subprocess
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SK = ROOT / "skills"
DIST = ROOT / "dist"
ORDER = ["gns3-server-api", "extreme-switch-templates", "switch-engine-in-gns3",
         "fabric-engine-in-gns3", "simulated-devices-in-gns3", "site-engine-in-gns3", "site-engine-flexview-builder",
         "extreme-product-docs"]
TITLE = "Claude Code skills for Extreme Networks labs on GNS3"

CSS = """
@page { size: A4; margin: 20mm 18mm 22mm 18mm;
  @bottom-left { content: "Community contribution · CC BY 4.0 · not an official Extreme Networks document";
                 font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 7.5pt; color: #7a7f8c; }
  @bottom-right { content: "Page " counter(page) " of " counter(pages);
                  font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 7.5pt; color: #7a7f8c; } }
* { box-sizing: border-box; }
body { font-family: 'Helvetica Neue', Arial, sans-serif; color: #1f2430; font-size: 10pt; line-height: 1.5; }
.cover { border-left: 6px solid #0b6e6e; padding: 4mm 0 4mm 6mm; margin-bottom: 8mm; }
.cover h1 { font-size: 22pt; margin: 0 0 2mm 0; color: #0b3d4a; border: none; }
.cover .sub { font-size: 11pt; color: #4a5160; }
.meta { width: 100%; border-collapse: collapse; margin: 0 0 8mm 0; font-size: 9pt; }
.meta td { padding: 1.6mm 2mm; border-bottom: 1px solid #e3e6ea; vertical-align: top; }
.meta td.k { width: 30mm; color: #0b6e6e; font-weight: 600; }
h2 { font-size: 15pt; color: #0b3d4a; border-bottom: 2px solid #0b6e6e; padding-bottom: 1mm;
     margin-top: 9mm; break-after: avoid; }
h2.skill { break-before: page; }
h3 { font-size: 12pt; color: #0b3d4a; margin-top: 6mm; break-after: avoid; }
h4 { font-size: 10.5pt; color: #0b3d4a; break-after: avoid; }
p.desc { background: #eef6f6; border-left: 3px solid #0b6e6e; padding: 2mm 3mm; font-style: italic; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.3pt; background: #f2f4f6;
       padding: 0 0.6mm; border-radius: 2px; }
pre { background: #f5f6f8; border: 1px solid #dfe3e8; border-radius: 3px; padding: 2.5mm 3mm;
      font-size: 8pt; line-height: 1.35; white-space: pre-wrap; word-break: break-all; break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 8pt; }
table { border-collapse: collapse; width: 100%; margin: 3mm 0; font-size: 8.6pt; break-inside: auto; }
th { background: #0b3d4a; color: white; text-align: left; padding: 1.5mm 2mm; }
td { border-bottom: 1px solid #e3e6ea; padding: 1.4mm 2mm; vertical-align: top; }
td code, th code { word-break: break-all; }
th code { background: rgba(255,255,255,0.18); color: #ffffff; }
tr { break-inside: avoid; }
li { margin: 0.8mm 0; }
a { color: #0b6e6e; text-decoration: none; }
hr { border: none; border-top: 1px solid #dfe3e8; margin: 6mm 0; }
"""


def demote(md):
    return re.sub(r"(?m)^(#{1,5}) ", lambda m: "#" + m.group(1) + " ", md)


def drop_h1(md):
    return re.sub(r"(?m)^# .*\n", "", md, count=1)


def main():
    parts = [(ROOT / "src" / "guide_intro.md").read_text()]
    readme = (ROOT / "README.md").read_text()
    keep = re.search(r"(## Install.*?)(?=## License)", readme, re.S).group(1)
    parts.append("## Installing and using the pack\n" + demote(keep).replace("### Install\n", "", 1))
    for name in ORDER:
        text = (SK / name / "SKILL.md").read_text()
        fm, body = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S).groups()
        desc = re.search(r"description: (.*)", fm).group(1)
        parts.append(f'<h2 class="skill">Skill <code>{name}</code></h2>\n\n'
                     f'<p class="desc">{desc}</p>\n\n' + demote(drop_h1(body)))
    ref = (SK / "simulated-devices-in-gns3/reference/lldpd_endpoints.md").read_text().split("\n", 1)[1]
    parts.append('<h2 class="skill">Appendix: <code>simulated-devices-in-gns3/reference/lldpd_endpoints.md</code></h2>\n'
                 + demote(ref))
    val = (ROOT / "VALIDATION.md").read_text().split("\n", 1)[1]
    parts.append('<h2 class="skill">Appendix: validation log</h2>\n' + demote(val))
    scripts = sorted(p.relative_to(SK) for p in SK.rglob("*.py"))
    parts.append("## Appendix: scripts in the zip\n\n" + "\n".join(
        f"- `{s}`: " + (SK / s).read_text().split('"""')[1].strip().splitlines()[0]
        for s in scripts))
    parts.append("## License\n\n" + re.search(r"## License\n(.*)", readme, re.S).group(1))
    md = "\n\n".join(parts)

    body = subprocess.run(["pandoc", "-f", "gfm", "-t", "html", "--no-highlight"], input=md,
                          capture_output=True, text=True, check=True).stdout
    # long code blocks may break across pages; short ones stay whole
    body = re.sub(r"(<pre>(?:(?!</pre>).)*?</pre>)",
                  lambda m: m.group(1).replace("<pre>", '<pre style="break-inside: auto">', 1)
                  if m.group(1).count("\n") > 18 else m.group(1), body, flags=re.S)
    today = datetime.date.today()
    head = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{TITLE}</title>
<style>{CSS}</style></head><body>
<div class="cover"><h1>{TITLE}</h1>
<div class="sub">Switch Engine · Fabric Engine · Site Engine — guide and full skill text</div></div>
<table class="meta">
<tr><td class="k">Assumes</td><td>Only the IP address of a working GNS3 server (API v2)</td></tr>
<tr><td class="k">Contents</td><td>8 skills: GNS3 API, switch templates, Switch Engine, Fabric Engine, simulated devices, Site Engine, FlexViews, product documentation</td></tr>
<tr><td class="k">Validated on</td><td>GNS3 2.2.45 · EXOS VM 32.6.3.126 · VOSS VM 9.4.0.0 · XIQ-SE 24.2.15.5 · Linux clients</td></tr>
<tr><td class="k">Author</td><td>Salva Ferrer (AVTN) · community contribution · {today:%Y-%m-%d}</td></tr>
<tr><td class="k">License</td><td>Text CC BY 4.0 · scripts MIT</td></tr>
</table>
"""
    DIST.mkdir(exist_ok=True)
    html_path = DIST / "extreme-gns3-skills-guide.html"
    html_path.write_text(head + body + "\n</body></html>\n")
    r = subprocess.run(["weasyprint", str(html_path), str(DIST / "extreme-gns3-skills-guide.pdf")],
                       capture_output=True, text=True)
    print(r.stderr[-1500:] or "pdf ok")

    with zipfile.ZipFile(DIST / "extreme-gns3-skills.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in [ROOT / "README.md", ROOT / "LICENSE", ROOT / "VALIDATION.md"] + sorted(SK.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                z.write(f, pathlib.Path("extreme-gns3-skills") / f.relative_to(ROOT))
    print("zip ok")


if __name__ == "__main__":
    main()
